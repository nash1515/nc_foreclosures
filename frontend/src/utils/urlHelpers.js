export const formatZillowUrl = (address) => {
  if (!address) return null;

  // Use proper URL encoding to match browser-generated search URLs
  // encodeURIComponent converts spaces to %20, then we replace with + for Zillow format
  // Commas become %2C, preserving address structure that Zillow expects
  const encoded = encodeURIComponent(address).replace(/%20/g, '+');

  return `https://www.zillow.com/homes/${encoded}_rb/`;
};
