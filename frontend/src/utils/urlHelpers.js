export const formatZillowUrl = (address) => {
  if (!address) return null;

  // Remove special characters and replace spaces with hyphens
  const formatted = address
    .replace(/[.,#]/g, '')
    .replace(/\s+/g, '-');

  return `https://www.zillow.com/homes/${formatted}_rb/`;
};
