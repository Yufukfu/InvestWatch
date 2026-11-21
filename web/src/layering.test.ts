/// <reference types="node" />
import { spawnSync } from 'node:child_process';
import { copyFileSync, mkdirSync, mkdtempSync, rmSync, writeFileSync } from 'node:fs';
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

function lint(rel: string) {
  return spawnSync(process.execPath, [oxlint, '-c', '.oxlintrc.json', '-f', 'unix', rel], { cwd: dir, encoding: 'utf8' });
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
  write(`${c}FromModel.tsx`, "import type { Row } from '../model';\nexport type A = Row;\n");
  write(`${c}FromSharedData.tsx`, "import { x } from '../../../shared/data/x';\nexport const A = x;\n");
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
  ])('rejects a component importing %s', (_name, file) => {
    const result = lint(`src/features/demo/components/${file}.tsx`);
    expect(result.status).not.toBe(0);
    expect(result.stdout).toContain('no-restricted-imports');
  });

  it.each([['model types', 'FromModel'], ['an unrelated shared/data folder', 'FromSharedData']])(
    'accepts a component importing %s',
    (_name, file) => {
      expect(lint(`src/features/demo/components/${file}.tsx`).status).toBe(0);
    },
  );

  it('accepts a props-only component', () => {
    expect(lint('src/features/demo/components/Props.tsx').status).toBe(0);
  });

  it('accepts a data hook importing the generated client', () => {
    expect(lint('src/features/demo/data/useDemo.ts').status).toBe(0);
  });
});
