/** ISBNs from what a barcode scanner reads: books are EAN-13 numbers starting 978 or 979. */

function validIsbn13(digits: string): boolean {
  if (!/^\d{13}$/.test(digits)) return false;
  const sum = [...digits.slice(0, 12)].reduce((total, digit, index) => total + Number(digit) * (index % 2 ? 3 : 1), 0);
  return (10 - (sum % 10)) % 10 === Number(digits[12]);
}

export function isbnFromBarcode(text: string | null | undefined): string | null {
  const digits = (text ?? "").replace(/\D/g, "");
  return digits.length === 13 && /^97[89]/.test(digits) && validIsbn13(digits) ? digits : null;
}
