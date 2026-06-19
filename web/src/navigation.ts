export type PageId =
  | "pipeline"
  | "parameters"
  | "training"
  | "evaluation"
  | "compare"
  | "registry"
  | "ops"
  | "benchmarks"
  | "simulation";

export interface NavItem {
  id: PageId;
  label: string;
  section?: string;
}

export const NAV_ITEMS: NavItem[] = [
  { id: "pipeline", label: "파이프라인 개요", section: "ML 파이프라인" },
  { id: "parameters", label: "파라미터 설정" },
  { id: "training", label: "학습" },
  { id: "evaluation", label: "검증·테스트 평가" },
  { id: "compare", label: "모델 비교" },
  { id: "registry", label: "모델 등록" },
  { id: "ops", label: "Export / Infer", section: "운영" },
  { id: "benchmarks", label: "벤치마크 분석", section: "분석" },
  { id: "simulation", label: "시뮬레이션 뷰어" },
];
