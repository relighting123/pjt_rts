export interface DatasetInfo {
  name: string;
  kind: "benchmark" | "inference";
}

export interface Kpis {
  plan_achievement: number;
  avg_utilization: number;
  total_move: number;
  conversion_count: number;
  converting_eqp_count: number;
}

export interface PerTask {
  task: string;
  plan: number;
  produced: number;
  rate: number;
}

export interface HourlyStat {
  hour: number;
  time: string;
  produce: number;
  cumulative: number;
  util_rate: number;
}

export interface GanttSegment {
  kind: "RUN" | "CONV";
  eqp_id: string;
  model: string;
  plan_prod_key: string;
  oper_id: string;
  batch_id: string;
  task: string;
  start: string;
  end: string;
  qty: number;
  from_batch?: string;
  to_batch?: string;
  from_task?: string;
  to_task?: string;
}

export interface ConversionRow {
  job_id: string;
  eqp_id: string;
  model: string;
  conv_start: string;
  conv_end: string;
  conv_time: number;
  from_batch: string;
  to_batch: string;
  from_ppk: string;
  to_ppk: string;
  status: string;
}

export interface AlgoView {
  kpis: Kpis;
  per_task: PerTask[];
  hourly: HourlyStat[];
  gantt: GanttSegment[];
  conversions: ConversionRow[];
}

export interface TaskInfo {
  plan_prod_key: string;
  oper_id: string;
  oper_seq: number;
  batch_id: string;
  plan_qty: number;
  init_wip: number;
}

export interface EquipmentInfo {
  eqp_id: string;
  eqp_model: string;
  batch_id: string;
  plan_prod_key: string;
  oper_id: string;
}

export interface GuideRow {
  task: string;
  model: string;
  target_count: number;
}

export interface DatasetDetail {
  name: string;
  meta: {
    rule_timekey: string;
    facid: string | null;
    horizon_hours: number;
    switch_time_hours: number;
    task_count: number;
    model_count: number;
    total_eqp: number;
    has_real_equipments: boolean;
    note: string;
  };
  tasks: TaskInfo[];
  equipments: EquipmentInfo[];
  optimal: number | null;
  guide: GuideRow[];
  algorithms: {
    heuristic: AlgoView | null;
    rl: AlgoView | null;
  };
}

export interface SummaryRow {
  name: string;
  heuristic: number | null;
  rl: number | null;
  optimal: number | null;
  gap: number | null;
  avg_utilization: number | null;
  total_move: number;
  conversion_count: number;
  horizon_hours: number;
  task_count: number;
  total_eqp: number;
  has_real_equipments: boolean;
}

export interface Summary {
  rows: SummaryRow[];
  averages: {
    heuristic: number | null;
    rl: number | null;
    optimal: number | null;
    gap: number | null;
    avg_utilization: number | null;
    avg_conversion_count: number | null;
  };
}
