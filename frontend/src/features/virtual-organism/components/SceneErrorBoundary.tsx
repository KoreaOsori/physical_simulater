"use client";

import { Component, type ReactNode } from "react";

/** WebGL을 못 쓰는 환경(오래된 GPU, 헤드리스 브라우저 등)에서 3D 장면이 던지는
 * 오류가 페이지 전체를 죽이지 않게 -- 대신 나침반 뷰로 돌아가라는 안내를 보인다. */
export class SceneErrorBoundary extends Component<{ children: ReactNode; fallback: ReactNode }, { failed: boolean }> {
  state = { failed: false };

  static getDerivedStateFromError() {
    return { failed: true };
  }

  componentDidCatch(error: unknown) {
    console.error("3D lab scene failed to render", error);
  }

  render() {
    return this.state.failed ? this.props.fallback : this.props.children;
  }
}
