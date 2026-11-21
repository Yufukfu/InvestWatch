/// <reference types="node" />
import { spawnSync } from 'node:child_process';
import { copyFileSync, mkdirSync, mkdtempSync, rmSync, writeFileSync } from 'node:fs';
import { tmpdir } from 'node:os';
import { dirname, join, resolve } from 'node:path';
import { afterAll, beforeAll, describe, expect, it } from 'vitest';

// ADR 0204: presentational components import nothing from the data layer. The rule lives in
// .oxlintrc.json; this test runs the installed oxlint with that real config over throwaway files.
const webRoot = resolve(import.meta.dirname, '..');
const oxlint = join(webRoot, 'node_modules', '.bin', 'oxlint');

let dir: string;

function write(rel: string, content: string) {
  const file = join(dir, rel);
  mkdirSync(dirname(file), { recursive: true });
  writeFileSync(file, content);
}

function lint(rel: string) {
  return spawnSync(oxlint, ['-c', '.oxlintrc.json', rel], { cwd: dir, encoding: 'utf8' });
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
  ])('rejects a component importing %s', (_name, file) => {
    const result = lint(`src/features/demo/components/${file}.tsx`);
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
