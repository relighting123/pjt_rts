export interface DatasetInfo {
  name: string;
  kind: "benchmark" | "inference";
}

export interface Kpis {
  plan_achievement: number;
  static_plan_achievement?: number;
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

export interface AllocationPivotRow {
  task: string;
  plan_prod_key: string;
  oper_id: string;
  counts: Record<string, number | null>;
  uphs: Record<string, number | null>;
  plan: number;
  produced: number;
  rate: number;
  dynamic_produced?: number;
  dynamic_rate?: number;
}

export interface AllocationPivot {
  models: string[];
  rows: AllocationPivotRow[];
}

export interface AlgoView {
  kpis: Kpis;
  per_task: PerTask[];
  hourly: HourlyStat[];
  gantt: GanttSegment[];
  conversions: ConversionRow[];
  allocation_pivot: AllocationPivot;
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

export interface InitAssignRow {
  eqp_model: string;
  plan_prod_key: string;
  oper_id: string;
  count: number;
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
  init_assign: InitAssignRow[];
  optimal: number | null;
  rl_status: {
    available: boolean;
    reason: "ready" | "model_missing" | "model_load_failed" | "shape_mismatch";
  };
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
  heuristic_utilization: number | null;
  rl_utilization: number | null;
  heuristic_conversion_count: number;
  rl_conversion_count: number;
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

export interface TrainingPoint {
  stage?: string;
  phase?: "bc" | "ppo";
  timesteps: number;
  mean_reward: number;
  loss?: number;
  episodes?: number;
}

export interface TrainingMetrics {
  stage: string;
  points: TrainingPoint[];
}

export interface OpsDefaults {
  facid: string | null;
  batchid: string | null;
  lookback_days: number;
  default_ppo_steps: number;
  horizon_hours: number;
}

export interface OpsArtifacts {
  dispatch_model: string;
  dispatch_model_exists: boolean;
  alloc_model: string;
  alloc_model_exists: boolean;
  train_json_count: number;
  inference_input_count: number;
  inference_result_count: number;
  ops_log: string;
}

export interface OpsJob {
  id: string;
  kind: "export" | "infer" | "train";
  status: "queued" | "running" | "done" | "failed";
  params: Record<string, unknown>;
  created_at: string;
  started_at: string | null;
  finished_at: string | null;
  result: Record<string, unknown> | null;
  error: string | null;
  log?: string | null;
}

export interface OpsStatus {
  defaults: OpsDefaults;
  artifacts: OpsArtifacts;
  busy: boolean;
  running_job: OpsJob | null;
}

export interface OpsLogEntry {
  ts?: string;
  event?: string;
  [key: string]: string | undefined;
}

export interface ExportRequest {
  mode: "single" | "train_range";
  timekey?: string | null;
  from_timekey?: string | null;
  to_timekey?: string | null;
  lookback_days?: number;
  horizon_hours?: number;
  facid?: string | null;
  batchid?: string | null;
  sample?: boolean;
}

export interface InferRequest {
  timekey?: string | null;
  facid?: string | null;
  batchid?: string | null;
  horizon_hours?: number;
  skip_input_export?: boolean;
  write_db?: boolean;
  conv_groups?: Record<string, string[]> | null;
}

export interface TrainRequest {
  mode: "local" | "db_range";
  from_timekey?: string | null;
  to_timekey?: string | null;
  lookback_days?: number;
  horizon_hours?: number;
  facid?: string | null;
  batchid?: string | null;
  steps?: number;
  conv_groups?: Record<string, string[]> | null;
}

export interface MlConfig {
  ppo_steps: number;
  bc_epochs: number;
  bc_lr: number;
  bc_loss_target: number;
  max_tasks: number;
  max_models: number;
  dwell_lambda: number;
  alloc_lambda: number;
  dwell_obs: boolean;
  use_alloc_model: boolean;
  guide_util_threshold: number;
  guide_band_pct: number;
  horizon_hours: number;
  lookback_days: number;
  metric_digits: number;
  conv_groups: Record<string, string[]>;
  env_locked?: string[];
  paths: Record<string, string>;
}

export interface ModelInfo {
  id: string;
  name: string;
  path: string;
  filename: string;
  size_bytes: number;
  modified_at: string;
  registered: boolean;
  is_active: boolean;
  exists: boolean;
  registered_at?: string;
  notes?: string;
  source_path?: string;
  final_training_reward?: number | null;
}

export interface EvalKpi {
  plan_achievement: number | null;
  avg_utilization: number;
  conversion_count: number;
}

export interface EvalRow {
  dataset: string;
  optimal: number | null;
  heuristic: EvalKpi | null;
  rl: EvalKpi | null;
  rl_episode_reward: number | null;
  rl_available: boolean;
}

export interface EvalResult {
  split: string;
  model_path: string | null;
  model_loaded: boolean;
  count: number;
  rows: EvalRow[];
  averages: {
    heuristic_plan_achievement: number | null;
    rl_plan_achievement: number | null;
    heuristic_utilization: number | null;
    rl_utilization: number | null;
    rl_episode_reward: number | null;
    optimal: number | null;
  };
}

// ── Simulation step-by-step ──

export interface SimWipRow {
  task_index: number;
  task: string;
  plan_prod_key: string;
  oper_id: string;
  wip: number;
  produced: number;
  plan: number;
  rate: number;
}

export interface SimAssignRow {
  model: string;
  task_index: number;
  task: string;
  count: number;
  switching: number;
}

export interface SimMove {
  model: string;
  from_index: number;
  to_index: number;
  from_task: string;
  to_task: string;
}

export interface SimState {
  session_id?: string;
  hour: number;
  total_hours: number;
  is_done: boolean;
  gantt: GanttSegment[];
  wip: SimWipRow[];
  assign: SimAssignRow[];
  valid_moves: SimMove[];
}

export interface ModelCompareRow {
  model_id: string;
  name?: string;
  path?: string;
  registered?: boolean;
  is_active?: boolean;
  averages?: EvalResult["averages"];
  count?: number;
  error?: string;
}

export interface PipelineStatus {
  config: MlConfig;
  models_count: number;
  active_model_id: string | null;
  active_model_exists: boolean;
  train_json_count: number;
  test_json_count: number;
  training_points: number;
  validation: EvalResult["averages"];
  test: EvalResult["averages"];
}
