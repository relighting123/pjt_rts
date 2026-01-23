from abc import ABC, abstractmethod
from typing import List, Dict, Tuple, Optional

class BaseScheduler(ABC):
    @abstractmethod
    def select_tasks(self, idle_eqs: list, context: dict) -> List[Tuple[object, Tuple[str, str], int]]:
        """
        Returns a list of (equipment, (product, process), co_time)
        """
        pass

class DBRScheduler(BaseScheduler):
    def __init__(self, buffer_size: int = 5):
        self.buffer_size = buffer_size
        self.drum_process = None

    def identify_drum(self, plan: dict, st: dict) -> Tuple[str, str]:
        loads = {key: qty * st.get(key, 10) for key, qty in plan.items() if qty > 0}
        if not loads:
            return list(st.keys())[0]
        return max(loads, key=loads.get)

    def get_co_time(self, eq, to_prod: str, to_proc: str, co_rules: list, default_co: int) -> int:
        if eq.current_product == to_prod and eq.current_process == to_proc:
            return 0
        if eq.current_product is None:
            return 0
        for rule in co_rules:
            if (rule['from_product'] == eq.current_product and 
                rule['from_process'] == eq.current_process and 
                rule['to_product'] == to_prod and 
                rule['to_process'] == to_proc):
                return rule['time']
        return default_co

    def select_tasks(self, idle_eqs, context) -> List[Tuple[object, Tuple[str, str], int]]:
        plan = context['plan']
        achieved = context['achieved']
        wip = context['wip']
        st = context['st']
        capabilities = context['capabilities']
        co_rules = context['co_rules']
        default_co = context['default_co']
        oper_seq = context['oper_seq']

        if not self.drum_process:
            self.drum_process = self.identify_drum(plan, st)

        tasks = list(plan.keys())
        def task_priority(task):
            if task == self.drum_process: return 0
            if oper_seq[task] > oper_seq[self.drum_process]: return 1
            return 2
        tasks.sort(key=task_priority)

        assignments = []
        local_wip = wip.copy()
        current_assignments = context.get('current_assignments', {})
        under_way = {task: achieved.get(task, 0) + current_assignments.get(task, 0) for task in tasks}
        
        # Station Potential: Immediate WIP + Upstream machines + Upstream WIP
        potential = {}
        for task in tasks:
            prod, proc = task
            imm = local_wip.get(task, 0)
            # In-process WIP: Machines currently working on upstream steps
            upstream_running = sum(current_assignments.get((prod, op_proc), 0) 
                                  for (op_prod, op_proc), op_seq_val in oper_seq.items() 
                                  if op_prod == prod and op_seq_val < oper_seq[task])
            # Material WIP: Unprocessed items upstream
            upstream_wip = sum(wip.get((prod, op_proc), 0) 
                              for (op_prod, op_proc), op_seq_val in oper_seq.items() 
                              if op_prod == prod and op_seq_val < oper_seq[task])
            potential[task] = imm + upstream_running + upstream_wip

        for eq in idle_eqs:
            best_task = None
            max_score = -999999
            
            for task in tasks:
                prod, proc = task
                capable = any(cap['model'] == eq.model.split('_')[0] and cap['product'] == prod and cap['process'] == proc 
                             for cap in capabilities)
                if not capable: continue
                
                # Flow-based logic refined
                imm_wip = local_wip.get(task, 0)
                is_resident = (eq.current_product == prod and eq.current_process == proc)
                
                # 1. Flow Score: High base for having immediate or near-future work
                if imm_wip > 0:
                    flow_score = 1000 + (imm_wip * 10)
                elif is_resident and potential[task] > 0:
                    # Moderate base to stay and wait for upstream work
                    flow_score = 800 + (potential[task] * 5)
                else:
                    flow_score = 0
                
                # 2. Resident Priority: Bonus to stay at station
                resident_bonus = 200 if is_resident else 0
                
                # 3. Changeover Penalty: Barrier to moving
                co_time = self.get_co_time(eq, prod, proc, co_rules, default_co)
                move_penalty = (co_time * 15) if not is_resident else 0
                
                # 4. Balancing: Discourage dogpiling beyond one machine per station 
                # unless WIP is high
                assigned_at_task = current_assignments.get(task, 0)
                balance_penalty = assigned_at_task * 500
                
                score = flow_score + resident_bonus - move_penalty - balance_penalty

                # Decision Gate
                if under_way[task] < plan[task]:
                    # Rope logic
                    if oper_seq[task] < oper_seq[self.drum_process]:
                        if local_wip[self.drum_process] >= self.buffer_size: continue

                    if score > max_score:
                        max_score = score
                        best_task = task
            
            if best_task:
                # If we chose a task and it has immediate WIP, assign it
                if local_wip[best_task] > 0:
                    co_time = self.get_co_time(eq, best_task[0], best_task[1], co_rules, default_co)
                    assignments.append((eq, best_task, co_time))
                    local_wip[best_task] -= 1
                    current_assignments[best_task] = current_assignments.get(best_task, 0) + 1
                    under_way[best_task] += 1
                else:
                    # Chose to stay and wait for Future WIP (Resident logic)
                    pass
                
        return assignments
