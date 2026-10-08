// Only exact source-version matches are supported until cross-version tests exist.
export function knownVersion(value) {
  if(typeof value !== 'string')return '';
  const version=value.trim().replace(/^v/i,'');
  return /^\d+\.\d+\.\d+(?:[-+][0-9A-Za-z.-]+)?$/.test(version) ? version : '';
}

export function matchesSourceVersion(asset, targetVersion) {
  const target=knownVersion(targetVersion);
  return !target || knownVersion(asset?.source_version) === target;
}

export function filterByVersion(assets, targetVersion, enabled=true) {
  return enabled && knownVersion(targetVersion) ? assets.filter(asset=>matchesSourceVersion(asset,targetVersion)) : assets;
}
