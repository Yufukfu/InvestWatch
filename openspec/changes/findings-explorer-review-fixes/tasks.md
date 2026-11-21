# Tasks

## 1. Review round 2 (@hen68, PR #39)

- [x] 1.1 Focus escapes the dialog when the refetch after a save fails: the detail renders a stable tree (alert slot and body slot), and a test saves with the refetch failing and asserts focus stays inside the dialog.
- [x] 1.2 Order-dependent test in `useFindings.test.tsx` ("a settled search replaces the history entry"): wait for the request to settle before the test ends.
- [x] 1.3 Inert-lift-before-focus test cannot fail: spy on the opener's `focus` and assert the page has no `inert` attribute at call time.
