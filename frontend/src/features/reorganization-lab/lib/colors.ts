import type { ClosedLoopController, ReorgStrategy } from "@/types/lab";

/** dataviz 기본 팔레트 어두운 모드 1~7번을 고정 순서로 배정(색은 전략을 따라간다 -- 선택한 전략 수가 바뀌어도 다시 칠하지 않음).
 * 이 앱 배경 #07140f에 대해 validate_palette.js로 검증: CVD ΔE 최저 8.4, 정상 시력 ΔE 최저 19.3, 대비 3:1 이상(7색도 같은 값으로 통과). */
export const STRATEGY_COLOR: Record<ReorgStrategy, string> = {
  none: "#3987e5",
  local: "#d95926",
  concentrated: "#199e70",
  distributed: "#c98500",
  normative: "#d55181",
  random: "#008300",
  tau: "#9085e9",
};

export const STRATEGY_SHORT: Record<ReorgStrategy, string> = {
  none: "없",
  local: "국",
  concentrated: "집",
  distributed: "분",
  normative: "정",
  random: "무",
  tau: "τ",
};

/** 같은 팔레트 1~3번(검증: CVD ΔE 9.4, 정상 시력 ΔE 26.5). */
export const CONTROLLER_COLOR: Record<ClosedLoopController, string> = {
  none: "#3987e5",
  open: "#d95926",
  closed: "#199e70",
};

export const CONTROLLER_LABEL: Record<ClosedLoopController, string> = {
  none: "개입 없음",
  open: "개방 루프(처음 계획)",
  closed: "폐루프(매 시기 피드백)",
};

/** 기준선(정상 뇌)은 계열 색이 아닌 본문 보조색 점선. */
export const REFERENCE_COLOR = "#8a9a8e";

export const CONTROLLER_SHORT: Record<ClosedLoopController, string> = {
  none: "개입 없음",
  open: "개방 루프",
  closed: "폐루프",
};
