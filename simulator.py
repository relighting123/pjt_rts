import json
import os
from dataclasses import dataclass, field
from typing import List, Dict, Tuple, Optional
from scheduler import BaseScheduler, DBRScheduler

@dataclass
class ChangeoverRule:
    from_prod: str
    from_proc: str
    to_prod: str
    to_proc: str
    time: int

class Equipment:
    def __init__(self, model: str, eq_id: str):
        self.model = model
        self.id = eq_id
        self.current_product = None
        self.current_process = None
        self.remaining_time = 0
        self.is_changing_over = False
        self.total_working_time = 0
        self.changeover_count = 0
        self.status = "IDLE" # IDLE, WORKING, CHANGEOVER
        self.prev_status = "IDLE"
        self.target_product = None
        self.target_process = None
        self.work_duration = 0

    def start_work(self, product: str, process: str, duration: int, co_time: int = 0):
        if co_time > 0:
            self.status = "CHANGEOVER"
            self.remaining_time = co_time
            self.is_changing_over = True
            self.changeover_count += 1
            self.target_product = product
            self.target_process = process
            self.work_duration = duration
        else:
            self.status = "WORKING"
            self.current_product = product
            self.current_process = process
            self.remaining_time = duration
            self.is_changing_over = False

    def step(self):
        if self.status == "IDLE":
            return None

        self.remaining_time -= 1
        if self.status == "WORKING":
            self.total_working_time += 1

        if self.remaining_time <= 0:
            if self.is_changing_over:
                self.status = "WORKING"
                self.current_product = self.target_product
                self.current_process = self.target_process
                self.remaining_time = self.work_duration
                self.is_changing_over = False
                return None
            else:
                result = (self.current_product, self.current_process)
                self.status = "IDLE"
                return result
        return None

class DBRSimulator:
    def __init__(self, data_dir: str, scheduler: BaseScheduler):
        self.data_dir = data_dir
        self.scheduler = scheduler
        self.load_data()
        self.init_state()

    def load_data(self):
        with open(os.path.join(self.data_dir, 'equipment_inventory.json'), 'r') as f:
            self.inventory = json.load(f)['inventory']
        with open(os.path.join(self.data_dir, 'equipment_capability.json'), 'r') as f:
            self.capabilities = json.load(f)['capabilities']
        with open(os.path.join(self.data_dir, 'plan_wip.json'), 'r') as f:
            self.production_data = json.load(f)['production']
        with open(os.path.join(self.data_dir, 'changeover_rules.json'), 'r') as f:
            co_data = json.load(f)
            self.default_co_time = co_data['default_time']
            self.co_rules = co_data['rules']

    def init_state(self):
        self.equipments: List[Equipment] = []
        for item in self.inventory:
            for i in range(item['count']):
                eq = Equipment(item['model'], f"{item['model']}_{i+1}")
                # Initial positions from capabilities (if count > 0)
                cap_counts = { (c['model'], c['product'], c['process']): c.get('initial_count', 0) for c in self.capabilities }
                for cap in self.capabilities:
                    key = (cap['model'], cap['product'], cap['process'])
                    if cap['model'] == item['model'] and cap_counts[key] > 0:
                        eq.current_product = cap['product']
                        eq.current_process = cap['process']
                        cap_counts[key] -= 1
                        break
                self.equipments.append(eq)

        self.wip: Dict[Tuple[str, str], int] = {}
        self.plan: Dict[Tuple[str, str], int] = {}
        self.achieved: Dict[Tuple[str, str], int] = {}
        self.oper_seq: Dict[Tuple[str, str], int] = {}
        self.st: Dict[Tuple[str, str], int] = {}
        all_prods = set()
        
        for p in self.production_data:
            key = (p['product'], p['process'])
            self.wip[key] = p['wip']
            self.plan[key] = p['plan']
            self.achieved[key] = 0
            self.oper_seq[key] = p['oper_seq']
            all_prods.add(p['product'])
            for cap in self.capabilities:
                if cap['product'] == p['product'] and cap['process'] == p['process']:
                    self.st[key] = cap['st']
                    break

        self.next_process = {}
        for prod in all_prods:
            procs = sorted([(self.oper_seq[k], k[1]) for k in self.oper_seq if k[0] == prod])
            for i in range(len(procs) - 1):
                self.next_process[(prod, procs[i][1])] = procs[i+1][1]
            self.next_process[(prod, procs[-1][1])] = "SHIPPING"

    def print_table_header(self):
        print(f"{'time':<6} | {'product':<10} | {'process':<10} | {'model':<10} | {'active':<8} | {'target':<8} | {'prod(after)':<12} | {'wip':<6} | {'capa':<6}")
        print("-" * 100)

    def print_allocation_row(self, t: int):
        model_capa = {}
        for eq in self.equipments:
            model_capa[eq.model] = model_capa.get(eq.model, 0) + 1

        eq_states = []
        for eq in self.equipments:
            eq_states.append({
                'model': eq.model,
                'status': eq.status,
                'curr': (eq.current_product, eq.current_process),
                'target': (eq.target_product, eq.target_process)
            })

        all_tasks = sorted(self.plan.keys(), key=lambda x: (x[0], self.oper_seq[x]))
        for task in all_tasks:
            prod, proc = task
            task_models = sorted(list(set(cap['model'] for cap in self.capabilities if cap['product'] == prod and cap['process'] == proc)))
            for model in task_models:
                allocated = sum(1 for s in eq_states if s['model'] == model and s['status'] in ("WORKING", "IDLE") and s['curr'] == task)
                target = sum(1 for s in eq_states if s['model'] == model and s['status'] == "CHANGEOVER" and s['target'] == task)
                ach_val = self.achieved.get(task, 0)
                wip_val = self.wip.get(task, 0)
                st_val = self.st.get(task, 10)
                cap_val = (allocated * 10) / st_val if st_val > 0 else 0.0
                print(f"{t:<6} | {prod:<10} | {proc:<10} | {model:<10} | {allocated:<8} | {target:<8} | {ach_val:<12} | {wip_val:<6} | {cap_val:<6.1f}")
        print("-" * 100)

    def run(self, total_minutes: int = 1440):
        print(f"\n{'='*20} DBR Simulation Started {'='*20}")
        self.print_table_header()
        
        for t in range(total_minutes + 1):
            for eq in self.equipments:
                finished = eq.step()
                if finished:
                    prod, proc = finished
                    self.achieved[(prod, proc)] += 1
                    next_proc = self.next_process.get((prod, proc))
                    if next_proc and next_proc != "SHIPPING":
                        self.wip[(prod, next_proc)] += 1

            idle_eqs = [eq for eq in self.equipments if eq.status == "IDLE"]
            if idle_eqs:
                idle_eqs.sort(key=lambda x: (x.current_product is None, x.current_product, x.current_process))
                current_assignments = {}
                for eq in self.equipments:
                    if eq.status == "WORKING":
                        current_assignments[(eq.current_product, eq.current_process)] = current_assignments.get((eq.current_product, eq.current_process), 0) + 1
                    elif eq.status == "CHANGEOVER":
                        current_assignments[(eq.target_product, eq.target_process)] = current_assignments.get((eq.target_product, eq.target_process), 0) + 1

                context = {
                    't': t, 'plan': self.plan, 'achieved': self.achieved, 'wip': self.wip, 'st': self.st,
                    'capabilities': self.capabilities, 'inventory': self.inventory, 'co_rules': self.co_rules,
                    'default_co': self.default_co_time, 'oper_seq': self.oper_seq, 'current_assignments': current_assignments
                }
                assignments = self.scheduler.select_tasks(idle_eqs, context)
                for eq, task, co_time in assignments:
                    prod, proc = task
                    self.wip[task] -= 1
                    eq.start_work(prod, proc, self.st[task], co_time)

            status_changed = any(eq.status != eq.prev_status for eq in self.equipments)
            if t == 0 or status_changed:
                self.print_allocation_row(t)

            any_active = any(eq.status in ("WORKING", "CHANGEOVER") for eq in self.equipments)
            all_final_done = True
            for prod in set(p for p, _ in self.plan):
                final_proc = max((p for p_prod, p in self.oper_seq if p_prod == prod), key=lambda p: self.oper_seq[(prod, p)])
                if self.achieved[(prod, final_proc)] < self.plan[(prod, final_proc)]:
                    all_final_done = False
                    break
            
            if not any_active and all_final_done:
                print(f"\n[Terminated] All final production targets met at {t} minutes.")
                if not status_changed: self.print_allocation_row(t)
                break

            for eq in self.equipments: eq.prev_status = eq.status
        
        self.t_total = t
        self.report()

    def report(self):
        print("\n=== Final Summary (Target Achievement per Product) ===")
        all_prods = sorted(list(set(p for p, _ in self.plan)))
        ach_rates = []
        for prod in all_prods:
            final_proc = max((p for p_prod, p in self.oper_seq if p_prod == prod), key=lambda p: self.oper_seq[(prod, p)])
            target = self.plan[(prod, final_proc)]
            actual = self.achieved[(prod, final_proc)]
            rate = (actual / target * 100) if target > 0 else 100.0
            ach_rates.append(rate)
            print(f"  Product {prod}: {actual}/{target} ({rate:.1f}%)")
        
        avg_achievement = sum(ach_rates) / len(ach_rates) if ach_rates else 0
        total_worked = sum(eq.total_working_time for eq in self.equipments)
        total_time = len(self.equipments) * (self.t_total if hasattr(self, 't_total') else 1440)
        utilization = (total_worked / total_time) * 100 if total_time > 0 else 0
        total_co = sum(eq.changeover_count for eq in self.equipments)
        
        print("-" * 30)
        print(f"Overall Product Achievement: {avg_achievement:.2f}%")
        print(f"Equipment Utilization:       {utilization:.2f}%")
        print(f"Total Changeover Count:      {total_co}")
        print("=" * 30)

if __name__ == "__main__":
    dbr_sched = DBRScheduler(buffer_size=5)
    sim = DBRSimulator(data_dir='data', scheduler=dbr_sched)
    sim.run()
