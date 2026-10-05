export const supportsBoolean = asset => !['curve','mixed'].includes(asset.kind);
export const componentMode = asset => supportsBoolean(asset) ? (asset.recipe ? 'sequence' : asset.insert_mode || 'new-body') : 'new-body';
