import rates from './tariff-rates.json';

export type TariffRates = {
  code: string;
  normal: string | null;
  mfn: string | null;
  vat: string | null;
  acfta: string | null;
  atiga: string | null;
  akfta: string | null;
  source: string;
};

/** Raw cells from the user-provided workbook. Conditions in cells are preserved. */
export function tariffRatesFor(code: string): TariffRates | null {
  const row = (rates as Record<string, (number | string | null)[]>)[code];
  if (!row) return null;
  return {
    code, normal: row[1] as string | null, mfn: row[2] as string | null,
    vat: row[3] as string | null, acfta: row[4] as string | null,
    atiga: row[5] as string | null, akfta: row[6] as string | null,
    source: `BIEU THUE XNK 2026.xlsx · sheet BT2026 · dòng ${row[0]}`,
  };
}
