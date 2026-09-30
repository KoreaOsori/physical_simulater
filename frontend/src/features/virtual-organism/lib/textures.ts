import * as THREE from "three";

/** 3D 실험실 장면(docs/44)용 절차적 텍스처. 외부 이미지/HDR을 받지 않는다 --
 * Docker/오프라인에서도 똑같이 그려지고, 라이선스 불확실한 에셋이 없다.
 * 전부 캔버스에 직접 그려 만든 "도식적 사실감"이지 실측 이미지가 아니다. */

function canvas(w: number, h: number): [HTMLCanvasElement, CanvasRenderingContext2D] {
  const c = document.createElement("canvas");
  c.width = w;
  c.height = h;
  const ctx = c.getContext("2d");
  if (!ctx) throw new Error("2D canvas context unavailable");
  return [c, ctx];
}

/** 결정적 의사난수 -- 매 렌더마다 텍스처가 바뀌지 않게. */
function rng(seed: number) {
  let s = seed >>> 0;
  return () => {
    s = (s * 1664525 + 1013904223) >>> 0;
    return s / 4294967296;
  };
}

function finish(c: HTMLCanvasElement, opts: { repeat?: number; srgb?: boolean } = {}): THREE.CanvasTexture {
  const tex = new THREE.CanvasTexture(c);
  if (opts.srgb !== false) tex.colorSpace = THREE.SRGBColorSpace;
  if (opts.repeat) {
    tex.wrapS = tex.wrapT = THREE.RepeatWrapping;
    tex.repeat.set(opts.repeat, opts.repeat);
  }
  tex.anisotropy = 4;
  tex.needsUpdate = true;
  return tex;
}

/** 얼룩덜룩한 표면(한천의 미세한 불균일, 실험대 에폭시 상판). */
export function makeSpeckleTexture(base: string, speck: string, density: number, seed: number, repeat = 1): THREE.CanvasTexture {
  const [c, ctx] = canvas(512, 512);
  const r = rng(seed);
  ctx.fillStyle = base;
  ctx.fillRect(0, 0, 512, 512);
  for (let i = 0; i < density; i++) {
    const x = r() * 512;
    const y = r() * 512;
    const rad = 0.5 + r() * 2.2;
    ctx.globalAlpha = 0.04 + r() * 0.1;
    ctx.fillStyle = speck;
    ctx.beginPath();
    ctx.arc(x, y, rad, 0, Math.PI * 2);
    ctx.fill();
  }
  // 큰 스케일의 부드러운 명암 변화
  for (let i = 0; i < 18; i++) {
    const x = r() * 512;
    const y = r() * 512;
    const g = ctx.createRadialGradient(x, y, 0, x, y, 60 + r() * 120);
    g.addColorStop(0, speck);
    g.addColorStop(1, "rgba(0,0,0,0)");
    ctx.globalAlpha = 0.035;
    ctx.fillStyle = g;
    ctx.fillRect(0, 0, 512, 512);
  }
  ctx.globalAlpha = 1;
  return finish(c, { repeat });
}

/** 초파리 복부: 황갈색 바탕에 체절마다 뒤쪽 가장자리의 흑갈색 띠(야생형
 * 암컷 복부의 전형적 줄무늬). 구(sphere) UV의 v가 몸 축을 따라가도록 쓴다. */
export function makeAbdomenTexture(): THREE.CanvasTexture {
  const [c, ctx] = canvas(256, 512);
  ctx.fillStyle = "#c8a266";
  ctx.fillRect(0, 0, 256, 512);
  const segments = 6;
  // v=0(위쪽) = 복부 앞(흉부 쪽), v=1 = 꽁무니
  for (let i = 0; i < segments; i++) {
    const y0 = 60 + (i * 400) / segments;
    const bandH = 400 / segments;
    const dark = 0.45 + (i / segments) * 0.5; // 꽁무니 쪽일수록 띠가 넓고 짙어짐
    const g = ctx.createLinearGradient(0, y0, 0, y0 + bandH);
    g.addColorStop(0, "rgba(58,36,18,0)");
    g.addColorStop(1 - dark * 0.6, "rgba(58,36,18,0)");
    g.addColorStop(1 - dark * 0.45, "rgba(52,32,16,0.92)");
    g.addColorStop(1, "rgba(40,24,12,0.95)");
    ctx.fillStyle = g;
    ctx.fillRect(0, y0, 256, bandH);
  }
  ctx.fillStyle = "rgba(40,24,12,0.9)";
  ctx.fillRect(0, 440, 256, 72);
  // 배 쪽(u의 절반)은 밝게 -- 등쪽 띠만 보이도록
  const belly = ctx.createLinearGradient(0, 0, 256, 0);
  belly.addColorStop(0, "rgba(214,190,140,0)");
  belly.addColorStop(0.35, "rgba(214,190,140,0)");
  belly.addColorStop(0.5, "rgba(214,190,140,0.85)");
  belly.addColorStop(0.65, "rgba(214,190,140,0)");
  belly.addColorStop(1, "rgba(214,190,140,0)");
  ctx.fillStyle = belly;
  ctx.fillRect(0, 0, 256, 512);
  return finish(c);
}

/** 겹눈: 짙은 적색 바탕에 육각 격자 낱눈(ommatidia) 하이라이트. */
export function makeCompoundEyeTexture(): THREE.CanvasTexture {
  const [c, ctx] = canvas(512, 256);
  ctx.fillStyle = "#8e1020";
  ctx.fillRect(0, 0, 512, 256);
  const r = 5.2;
  const dx = r * Math.sqrt(3);
  const dy = r * 1.5;
  for (let row = 0; row * dy < 256 + r; row++) {
    for (let col = 0; col * dx < 512 + r; col++) {
      const x = col * dx + (row % 2 ? dx / 2 : 0);
      const y = row * dy;
      const g = ctx.createRadialGradient(x - 1, y - 1, 0, x, y, r);
      g.addColorStop(0, "rgba(236,90,96,0.95)");
      g.addColorStop(0.55, "rgba(170,24,38,0.9)");
      g.addColorStop(1, "rgba(70,6,14,0.95)");
      ctx.fillStyle = g;
      ctx.beginPath();
      for (let k = 0; k < 6; k++) {
        const a = (Math.PI / 3) * k + Math.PI / 6;
        const px = x + Math.cos(a) * r * 0.96;
        const py = y + Math.sin(a) * r * 0.96;
        if (k === 0) ctx.moveTo(px, py);
        else ctx.lineTo(px, py);
      }
      ctx.closePath();
      ctx.fill();
    }
  }
  return finish(c);
}

/** 날개: 투명 막 + 초파리 날개맥(L1-L5 종맥, 전·후 횡맥)의 대략적 배치.
 * 날개 윤곽 좌표계(0-1)는 FlyModel의 날개 ShapeGeometry와 맞춘다. */
export function makeWingTexture(): THREE.CanvasTexture {
  const W = 512;
  const H = 192;
  const [c, ctx] = canvas(W, H);
  ctx.clearRect(0, 0, W, H);
  const g = ctx.createLinearGradient(0, 0, W, 0);
  g.addColorStop(0, "rgba(120,110,90,0.7)");
  g.addColorStop(0.3, "rgba(196,202,210,0.42)");
  g.addColorStop(1, "rgba(214,220,228,0.34)");
  ctx.fillStyle = g;
  ctx.fillRect(0, 0, W, H);

  ctx.strokeStyle = "rgba(70,55,35,0.85)";
  ctx.lineCap = "round";
  const vein = (pts: [number, number][], w: number) => {
    ctx.lineWidth = w;
    ctx.beginPath();
    pts.forEach(([x, y], i) => (i === 0 ? ctx.moveTo(x * W, y * H) : ctx.lineTo(x * W, y * H)));
    ctx.stroke();
  };
  // 앞가장자리(costa) + 종맥 L1..L5 (날개 뿌리 x=0 -> 끝 x=1, y=0.5 부근이 중심)
  vein([[0.02, 0.2], [0.35, 0.1], [0.62, 0.12]], 3.2); // costa / L1
  vein([[0.05, 0.3], [0.5, 0.22], [0.9, 0.3]], 2.2); // L2
  vein([[0.05, 0.42], [0.55, 0.4], [0.98, 0.5]], 2.2); // L3
  vein([[0.08, 0.52], [0.55, 0.6], [0.93, 0.72]], 2.0); // L4
  vein([[0.1, 0.62], [0.5, 0.78], [0.72, 0.88]], 1.8); // L5
  vein([[0.38, 0.41], [0.38, 0.58]], 1.6); // 전횡맥(acv)
  vein([[0.6, 0.64], [0.58, 0.8]], 1.6); // 후횡맥(pcv)
  return finish(c);
}

/** 여과지(냄새원 원판): 흰 섬유질 + 중앙의 젖은 얼룩. */
export function makeFilterPaperTexture(): THREE.CanvasTexture {
  const [c, ctx] = canvas(256, 256);
  const r = rng(11);
  ctx.fillStyle = "#f3f1ea";
  ctx.fillRect(0, 0, 256, 256);
  ctx.strokeStyle = "rgba(160,150,130,0.18)";
  for (let i = 0; i < 700; i++) {
    const x = r() * 256;
    const y = r() * 256;
    const a = r() * Math.PI;
    const l = 4 + r() * 10;
    ctx.lineWidth = 0.6;
    ctx.beginPath();
    ctx.moveTo(x, y);
    ctx.lineTo(x + Math.cos(a) * l, y + Math.sin(a) * l);
    ctx.stroke();
  }
  const wet = ctx.createRadialGradient(128, 128, 10, 128, 128, 110);
  wet.addColorStop(0, "rgba(200,185,140,0.55)");
  wet.addColorStop(0.7, "rgba(200,185,140,0.25)");
  wet.addColorStop(1, "rgba(200,185,140,0)");
  ctx.fillStyle = wet;
  ctx.fillRect(0, 0, 256, 256);
  return finish(c);
}

/** 금속자(mm 눈금) -- 실제 크기 감각을 주는 소품. lengthMm만큼의 눈금을 그린다. */
export function makeRulerTexture(lengthMm: number): THREE.CanvasTexture {
  const pxPerMm = 16;
  const W = lengthMm * pxPerMm + 32;
  const H = 96;
  const [c, ctx] = canvas(W, H);
  const g = ctx.createLinearGradient(0, 0, 0, H);
  g.addColorStop(0, "#d9dcdf");
  g.addColorStop(0.5, "#b9bec3");
  g.addColorStop(1, "#cfd3d7");
  ctx.fillStyle = g;
  ctx.fillRect(0, 0, W, H);
  ctx.fillStyle = "#1d1f22";
  ctx.font = "bold 18px monospace";
  ctx.textAlign = "center";
  for (let mm = 0; mm <= lengthMm; mm++) {
    const x = 16 + mm * pxPerMm;
    const len = mm % 10 === 0 ? 40 : mm % 5 === 0 ? 28 : 16;
    ctx.fillRect(x - 1, 0, 2, len);
    if (mm % 10 === 0) ctx.fillText(String(mm / 10), x, 64);
  }
  ctx.font = "14px monospace";
  ctx.textAlign = "right";
  ctx.fillText("cm", W - 8, 88);
  return finish(c);
}
