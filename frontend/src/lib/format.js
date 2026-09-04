// Money is paise everywhere in the API; format to Indian-grouped rupees here.
export const inr = (paise, decimals = 0) =>
  "₹" +
  ((paise || 0) / 100).toLocaleString("en-IN", {
    minimumFractionDigits: decimals,
    maximumFractionDigits: decimals,
  });

export const compactInr = (paise) => {
  const r = (paise || 0) / 100;
  if (r >= 1e7) return "₹" + (r / 1e7).toFixed(2) + "Cr";
  if (r >= 1e5) return "₹" + (r / 1e5).toFixed(2) + "L";
  if (r >= 1e3) return "₹" + (r / 1e3).toFixed(r >= 1e4 ? 0 : 1) + "k";
  return "₹" + Math.round(r);
};

export const pct = (x) => (x * 100).toFixed(1) + "%";

export const titleCase = (s) =>
  (s || "").replace(/_/g, " ").replace(/\b\w/g, (c) => c.toUpperCase());

export const num = (n) => (n || 0).toLocaleString("en-IN");
