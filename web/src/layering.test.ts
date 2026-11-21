/// <reference types="node" />
import { spawnSync } from 'node:child_process';
import { copyFileSync, existsSync, mkdirSync, mkdtempSync, readdirSync, readFileSync, rmSync, writeFileSync } from 'node:fs';
import { tmpdir } from 'node:os';
import { dirname, join, resolve } from 'node:path';
import { afterAll, beforeAll, describe, expect, it } from 'vitest';

// ADR 0204: presentational components import nothing from the data layer. The rule lives in
// .oxlintrc.json; this test runs the installed oxlint with that real config over throwaway files.
const webRoot = resolve(import.meta.dirname, '..');
const oxlint = join(webRoot, 'node_modules', 'oxlint', 'bin', 'oxlint');

let dir: string;

function write(rel: string, content: string) {
  const file = join(dir, rel);
  mkdirSync(dirname(file), { recursive: true });
  writeFileSync(file, content);
}

function lint(rel: string, cwd: string = dir, config = '.oxlintrc.json') {
  return spawnSync(process.execPath, [oxlint, '-c', config, '-f', 'unix', rel], { cwd, encoding: 'utf8' });
}

beforeAll(() => {
  dir = mkdtempSync(join(tmpdir(), 'layering-'));
  copyFileSync(join(webRoot, '.oxlintrc.json'), join(dir, '.oxlintrc.json'));
  const c = 'src/features/demo/components/';
  write(`${c}FromApi.tsx`, "import { useGetHealthQuery } from '../../../api/generated';\nexport const A = useGetHealthQuery;\n");
  write(`${c}FromData.tsx`, "import { useDemo } from '../data/useDemo';\nexport const A = useDemo;\n");
  write(`${c}FromStore.tsx`, "import { store } from '../../../store';\nexport const A = store;\n");
  write(`${c}FromRedux.tsx`, "import { useSelector } from 'react-redux';\nexport const A = useSelector;\n");
  write(`${c}FromToolkit.tsx`, "import { configureStore } from '@reduxjs/toolkit';\nexport const A = configureStore;\n");
  write(`${c}FromPage.tsx`, "import { DemoPage } from '../DemoPage';\nexport const A = DemoPage;\n");
  write(`${c}FromOtherFeature.tsx`, "import { useOther } from '../../other/data/useOther';\nexport const A = useOther;\n");
  write(`${c}TypeFromApi.tsx`, "import type { Finding } from '../../../api/generated';\nexport type A = Finding;\n");
  write('src/features/demo/components/sub/Nested.tsx', "import { useOther } from '../../../other/data/useOther';\nexport const A = useOther;\n");
  write(`${c}FromPageExt.tsx`, "import { DemoPage } from '../DemoPage.tsx';\nexport const A = DemoPage;\n");
  write(`${c}FromReduxSub.tsx`, "import { x } from 'react-redux/es/x';\nexport const A = x;\n");
  write(`${c}FromToolkitSub.tsx`, "import { x } from '@reduxjs/toolkit/dist/query/react';\nexport const A = x;\n");
  write(`${c}FromSocketSub.tsx`, "import { x } from 'socket.io-client/dist/x';\nexport const A = x;\n");
  write(`${c}FromApiBare.tsx`, "import * as api from '../../../api';\nexport const A = api;\n");
  write(`${c}FromDataBare.tsx`, "import * as data from '../data';\nexport const A = data;\n");
  write(`${c}FromStoreExt.tsx`, "import { store } from '../../../store.ts';\nexport const A = store;\n");
  write(`${c}FromSocketBare.tsx`, "import { io } from 'socket.io-client';\nexport const A = io;\n");
  write(`${c}FromModel.tsx`, "import type { Row } from '../model';\nexport type A = Row;\n");
  write(`${c}Props.tsx`, "import type { ReactNode } from 'react';\nexport const A = ({ children }: { children: ReactNode }) => children;\n");
  write('src/features/demo/data/useDemo.ts', "import { useGetHealthQuery } from '../../../api/generated';\nexport const useDemo = useGetHealthQuery;\n");
});

afterAll(() => rmSync(dir, { recursive: true, force: true }));

describe('feature layering (ADR 0204)', () => {
  it.each([
    ['api', 'FromApi'],
    ['data hook', 'FromData'],
    ['store', 'FromStore'],
    ['react-redux', 'FromRedux'],
    ['@reduxjs/toolkit', 'FromToolkit'],
    ['a page', 'FromPage'],
    ['a data hook of another feature', 'FromOtherFeature'],
    ['a DTO type from api (type-only)', 'TypeFromApi'],
    ['the api folder itself', 'FromApiBare'],
    ['the data folder itself', 'FromDataBare'],
    ['the store with a file extension', 'FromStoreExt'],
    ['socket.io-client', 'FromSocketBare'],
    ['a page with a file extension', 'FromPageExt'],
    ['a react-redux subpath', 'FromReduxSub'],
    ['a @reduxjs/toolkit subpath', 'FromToolkitSub'],
    ['a socket.io-client subpath', 'FromSocketSub'],
  ])('rejects a component importing %s', (_name, file) => {
    const result = lint(`src/features/demo/components/${file}.tsx`);
    expect(result.status).not.toBe(0);
    expect(result.stdout).toContain('no-restricted-imports');
  });

  it.each([['model types', 'FromModel']])(
    'accepts a component importing %s',
    (_name, file) => {
      expect(lint(`src/features/demo/components/${file}.tsx`).status).toBe(0);
    },
  );

  it('rejects a nested component importing another feature\'s data hook', () => {
    const result = lint('src/features/demo/components/sub/Nested.tsx');
    expect(result.status).not.toBe(0);
    expect(result.stdout).toContain('no-restricted-imports');
  });

  it('accepts a props-only component', () => {
    expect(lint('src/features/demo/components/Props.tsx').status).toBe(0);
  });

  it('accepts a data hook importing the generated client', () => {
    expect(lint('src/features/demo/data/useDemo.ts').status).toBe(0);
  });
});

// The synthetic cases above prove the config. These prove the real components obey it, so a CI that
// runs only `npm test` still catches a violation (the lint step is not the only line of defence).
describe('real feature components', () => {
  const featuresDir = join(webRoot, 'src', 'features');
  const componentDirs = readdirSync(featuresDir)
    .map((feature) => join('src', 'features', feature, 'components'))
    .filter((rel) => existsSync(join(webRoot, rel)));

  it('has component folders to check', () => {
    expect(componentDirs.length).toBeGreaterThanOrEqual(3);
  });

  it('pass the layering rule', () => {
    for (const rel of componentDirs) expect(lint(rel, webRoot).status, rel).toBe(0);
  });

  it('would catch a real component that imports the generated client', () => {
    const real = join(webRoot, 'src', 'features', 'findings', 'components', 'FindingsTable.tsx');
    const target = join(dir, 'src', 'features', 'findings', 'components', 'FindingsTable.tsx');
    mkdirSync(dirname(target), { recursive: true });
    writeFileSync(target, `import { useGetFindingsQuery } from '../../../api/generated';\n${readFileSync(real, 'utf8')}\nexport const leak = useGetFindingsQuery;\n`);
    expect(lint('src/features/findings/components/FindingsTable.tsx').status).not.toBe(0);
  });
});
