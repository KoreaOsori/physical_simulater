/** Standard cytogenetic-ideogram stain colors (the same convention used by
 * UCSC Genome Browser and most karyotype diagrams) — real classification
 * from the vendored cytoBand.txt `stain` column, not an invented palette. */
export const STAIN_COLOR: Record<string, string> = {
  gneg: "#e8ede9",
  gpos25: "#b7c2ba",
  gpos50: "#8a988e",
  gpos75: "#5c6d61",
  gpos100: "#2c352f",
  acen: "#c1584a", // centromere
  gvar: "#8a7a5c",
  stalk: "#6f92a8",
};

export function colorForStain(stain: string): string {
  return STAIN_COLOR[stain] ?? "#5c6d61";
}
