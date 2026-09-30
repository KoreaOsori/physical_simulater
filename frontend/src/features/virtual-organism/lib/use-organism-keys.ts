"use client";

import { useEffect, useRef, useState } from "react";

/** 폐루프 페이지의 키 입력(docs/45). 화면 버튼은 두지 않는다 -- 단축키와 중복되는
 * 온스크린 컨트롤을 만들지 않는 이 프로젝트 관행.
 *
 * - 방향키: 카메라 시선(←→ 좌우 회전, ↑↓ 위아래). 자동/수동 모두.
 * - W: 수동 조종에서 카메라가 보는 방향으로 전진(개체가 그쪽으로 몸을 돌리며 이동).
 * - Space: 초파리 비행(누르는 동안 상승, 떼면 서서히 하강·착지).
 * A/S/D는 일부러 없다 -- 옆걸음은 이 동물들에게 없는 움직임이고, 후진은 사람이
 * 시키는 게 아니라 뇌가 결정하는 고유 행동(pirouette/회피)이기 때문. */

export interface OrganismKeys {
  left: boolean;
  right: boolean;
  up: boolean;
  down: boolean;
  forward: boolean;
  fly: boolean;
}

const EMPTY: OrganismKeys = { left: false, right: false, up: false, down: false, forward: false, fly: false };

const KEY_MAP: Record<string, keyof OrganismKeys> = {
  arrowleft: "left",
  arrowright: "right",
  arrowup: "up",
  arrowdown: "down",
  w: "forward",
  " ": "fly",
};

export function useOrganismKeys() {
  const keysRef = useRef<OrganismKeys>({ ...EMPTY });
  const [pressed, setPressed] = useState<OrganismKeys>(EMPTY);

  useEffect(() => {
    const k = keysRef.current;
    const isTyping = (e: KeyboardEvent) => {
      const t = e.target as HTMLElement | null;
      return !!t && (t.tagName === "INPUT" || t.tagName === "TEXTAREA" || t.tagName === "SELECT" || t.isContentEditable);
    };
    const sync = () => setPressed({ ...k });
    const onDown = (e: KeyboardEvent) => {
      if (isTyping(e) || e.ctrlKey || e.metaKey || e.altKey) return;
      const name = KEY_MAP[e.key.toLowerCase()];
      if (!name) return;
      // 방향키 = 페이지 스크롤, Space = 포커스된 버튼 클릭 -- 둘 다 막아야 조종 중
      // 페이지가 튀거나 '자동 재생' 같은 버튼이 눌리지 않는다.
      e.preventDefault();
      if (!k[name]) {
        k[name] = true;
        sync();
      }
    };
    const onUp = (e: KeyboardEvent) => {
      const name = KEY_MAP[e.key.toLowerCase()];
      if (!name) return;
      if (!isTyping(e)) e.preventDefault();
      k[name] = false;
      sync();
    };
    const onBlur = () => {
      Object.assign(k, EMPTY);
      sync();
    };
    window.addEventListener("keydown", onDown);
    window.addEventListener("keyup", onUp);
    window.addEventListener("blur", onBlur);
    return () => {
      window.removeEventListener("keydown", onDown);
      window.removeEventListener("keyup", onUp);
      window.removeEventListener("blur", onBlur);
    };
  }, []);

  return { keysRef, pressed };
}
