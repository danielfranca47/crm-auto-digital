export function leadDisplayName(lead: { contactName?: string | null; companyName?: string | null }): string {
  const contactName = (lead.contactName ?? '').trim();
  const companyName = (lead.companyName ?? '').trim();

  if (contactName && companyName) return `${companyName} - ${contactName}`;
  if (contactName) return contactName;
  if (companyName) return companyName;
  return 'Lead sem nome';
}
