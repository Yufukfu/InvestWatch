// RTK Query code generation from the contract snapshot (src/api/openapi.json).
// Run: npm run api:generate (runs contracts:sync first). Never edit src/api/generated.ts by hand.
/** @type {import('@rtk-query/codegen-openapi').ConfigFile} */
module.exports = {
  schemaFile: './src/api/openapi.json',
  apiFile: './src/api/baseApi.ts',
  apiImport: 'baseApi',
  outputFile: './src/api/generated.ts',
  exportName: 'investWatchApi',
  hooks: { queries: true, lazyQueries: true, mutations: true },
  tag: true,
};
