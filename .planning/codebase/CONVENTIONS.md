# Coding Conventions

> **SUPERSEDED (2026-07-08):** describes the February v1; the shipped system is the root app/ FastAPI+Jinja build - see docs/reviews/2026-07-07-full-system-review.md

**Analysis Date:** 2026-02-03

## Naming Patterns

**Files:**
- React components: PascalCase (e.g., `ProjectsPage.tsx`, `Sidebar.tsx`, `Button.tsx`)
- Hooks: camelCase with `use` prefix (e.g., `useProjects.ts`, `useAuth.ts`, `useDashboard.ts`)
- Services: camelCase (e.g., `api.ts`)
- Stores: camelCase with `Store` suffix (e.g., `projectStore.ts`, `authStore.ts`)
- Types: camelCase (e.g., `index.ts` in types directory)
- Test files: `.spec.ts` suffix for e2e tests (e.g., `admin-e2e.spec.ts`)
- Page objects (e2e): PascalCase with `.page.ts` suffix (e.g., `login.page.ts`, `dashboard.page.ts`)

**Functions:**
- Components: PascalCase (export as default or named)
- Hooks: camelCase with `use` prefix
- Utility functions: camelCase
- Event handlers: camelCase starting with `handle` prefix (e.g., `handleCreate`, `handleNavigation`)

**Variables:**
- Constants: camelCase or UPPERCASE for truly immutable values
- Store actions: camelCase verbs (e.g., `setCurrentProject`, `updateProject`, `addProject`)
- Query keys: camelCase (e.g., `QUERY_KEY = 'projects'`)
- React state: camelCase with prefix describing what it is (e.g., `isModalOpen`, `newProject`)

**Types:**
- Interfaces: PascalCase, no `I` prefix (e.g., `ProjectState`, `ButtonProps`, `NavItem`)
- Union types: PascalCase (e.g., `ProjectStatus`, `UserRole`, `DocumentStatus`)
- Types imported with `type` keyword (e.g., `import type { Project }`)

**Interface & Component Props:**
- Props interface extends base HTML elements where applicable (e.g., `ButtonProps extends ButtonHTMLAttributes<HTMLButtonElement>`)
- All props documented as part of interface definition
- Optional props marked with `?` in interface

## Code Style

**Formatting:**
- No explicit ESLint config file found; using defaults
- ESLint configured for TypeScript (`@typescript-eslint/parser`, `@typescript-eslint/eslint-plugin`)
- React Refresh plugin enabled (`eslint-plugin-react-refresh`)
- React Hooks linting enabled (`eslint-plugin-react-hooks`)
- Linting rule: `--max-warnings 0` enforces zero warnings
- No Prettier configuration found; format manually or rely on IDE defaults

**Linting:**
- Command: `npm run lint` - `eslint . --ext ts,tsx --report-unused-disable-directives --max-warnings 0`
- TypeScript strict mode enabled in `tsconfig.json`
- `noUnusedLocals: true` - unused variables flagged as errors
- `noUnusedParameters: true` - unused parameters flagged as errors
- `noFallthroughCasesInSwitch: true` - enforces switch case completeness
- `skipLibCheck: true` - skips type checking of declaration files

**Styling:**
- Tailwind CSS for component styling
- Custom colors defined in `tailwind.config.js`: primary and accent color palettes
- Font: Inter system font family
- Utility-first approach with class concatenation using `clsx` library
- Component-level variant styles defined as TypeScript objects (see Button, Input components)

## Import Organization

**Order:**
1. React and core library imports (`react`, `react-dom`, `react-router-dom`, etc.)
2. Third-party library imports (`axios`, `zustand`, `@tanstack/react-query`, etc.)
3. Heroicons and UI library imports (`@heroicons/react`, `react-hot-toast`)
4. Relative imports using `@/` alias (components, hooks, services, store, types, utils)
5. Type imports separated with `import type` syntax

**Path Aliases:**
- `@/*` resolves to `src/*` (defined in `tsconfig.json` and `vite.config.ts`)
- Used consistently across all imports for cleaner relative paths

**Example:**
```typescript
import { BrowserRouter, Routes, Route, Navigate } from 'react-router-dom';
import { Toaster } from 'react-hot-toast';
import MainLayout from '@/components/layout/MainLayout';
import DashboardPage from '@/pages/DashboardPage';
import { useProjectStore } from '@/store/projectStore';
import type { Project } from '@/types';
```

## Error Handling

**Patterns:**
- React Query mutations use `onError` callbacks for centralized error handling
- Toast notifications for user-facing error messages: `toast.error(error.message || 'Fallback message')`
- Error messages include fallback text when specific message unavailable
- Try-catch blocks used in async helpers (`uploadFile`, `downloadFile` in `api.ts`)
- API responses wrapped in generic types for type safety
- Form handling with try-catch in async handlers (e.g., `handleCreate` in ProjectsPage)

**API Error Handling:**
```typescript
onError: (error: Error) => {
  toast.error(error.message || 'Failed to create project');
}
```

**File Operations:**
```typescript
try {
  // operation
} catch (error) {
  // handle or throw
}
```

## Logging

**Framework:** No explicit logging library; uses browser console and test helpers

**Patterns:**
- Console output in test utilities for feedback (e.g., `console.log()` in screenshot functions)
- Screenshot naming and timestamps logged for debugging
- API requests not explicitly logged; use browser network tab
- No structured logging format observed in source code

**Test Logging Example:**
```typescript
console.log(`📸 Screenshot saved: ${filename}`);
```

## Comments

**When to Comment:**
- Comments rare in component code; code structure is self-documenting
- JSDoc/TSDoc comments not used in source code
- Section comments in large components to separate logical regions (see Sidebar.tsx with `{/* Logo */}`, `{/* Navigation */}` comments)
- Test file headers include comprehensive test suite documentation

**Comment Style:**
- HTML-style comments in JSX for section separation
- No block comment convention for explaining complex logic
- Inline comments minimal; naming and structure preferred

**Test Documentation:**
```typescript
/**
 * BidOps AI - Comprehensive Admin E2E Test Suite
 *
 * Test Flow:
 * 1. Authentication & Login
 * 2. Dashboard Verification
 * ...
 */
```

## Function Design

**Size:**
- Components range from 10 to 150+ lines
- Helper functions kept concise (10-40 lines typically)
- Hooks typically 20-50 lines per export
- Each hook handles one concern (query, mutation, or side effect)

**Parameters:**
- Destructured parameters for objects when possible
- TypeScript interfaces always defined for component props
- Default parameters used for optional values (e.g., `page = 1, pageSize = 20`)
- Function overloading not used; single implementations with union types where needed

**Return Values:**
- React components return JSX
- Hooks return React Query objects, state setters, or mutations
- Helpers return promises or primitives
- Error handling deferred to callers or UI layer (toasts)

## Module Design

**Exports:**
- Components exported as default export from their files
- Hooks exported as named exports (multiple hooks per file)
- Utilities exported as named exports
- Barrel files used in layout and UI components for batch re-exports

**Barrel Files:**
- `src/components/layout/index.ts` - exports all layout components
- `src/components/ui/index.ts` - exports all UI components
- `src/hooks/index.ts` - exports all hooks
- Simplifies imports: `import { Button, Input } from '@/components/ui'`

**File Structure Example:**
```typescript
// Single hook file exports multiple related hooks
export function useProjects() { }
export function useProject() { }
export function useCreateProject() { }
export function useUpdateProject() { }
export function useDeleteProject() { }
export function useIngestProject() { }
```

## Reusable Components

**Base UI Components:**
- Located in `src/components/ui/`
- Accept standard HTML attributes via spread props
- Use `forwardRef` for ref forwarding (Button, Input)
- Variants and sizes defined as prop enums
- Loading and disabled states built-in
- Styling via Tailwind with `clsx` for conditional classes

**Example (Button):**
```typescript
export interface ButtonProps extends ButtonHTMLAttributes<HTMLButtonElement> {
  variant?: 'primary' | 'secondary' | 'danger' | 'outline' | 'ghost';
  size?: 'sm' | 'md' | 'lg';
  isLoading?: boolean;
}
```

**Layout Components:**
- `src/components/layout/MainLayout.tsx` - primary app shell
- `src/components/layout/Sidebar.tsx` - navigation
- `src/components/layout/Header.tsx` - top bar

## State Management

**Framework:** Zustand for client state

**Patterns:**
- Store actions named with verb prefixes (`set`, `update`, `add`, `remove`)
- Store state typed with interface extending action methods
- Subscriptions via hooks: `useProjectStore((state) => state.currentProject)`
- Mutations trigger React Query invalidation for server sync

**Example:**
```typescript
interface ProjectState {
  currentProject: Project | null;
  projects: Project[];
  // ... actions
}

export const useProjectStore = create<ProjectState>()((set) => ({
  // initial state and actions
}));
```

## Query/Data Fetching

**Framework:** React Query (TanStack Query) v5

**Patterns:**
- Named query keys as constants: `const QUERY_KEY = 'projects'`
- Query key arrays include parameters for uniqueness: `[QUERY_KEY, page, pageSize]`
- Mutations return typed response data
- `onSuccess` callbacks invalidate related queries and update store
- Loading states accessed via `isLoading` from query
- Error handling via `onError` callback with toast notifications

**Example:**
```typescript
export function useProjects(page = 1, pageSize = 20) {
  return useQuery({
    queryKey: [QUERY_KEY, page, pageSize],
    queryFn: async () => {
      const response = await api.get<PaginatedResponse<Project>>('/projects');
      return response.data;
    },
  });
}
```

## Type Safety

**Level:** Full TypeScript strict mode

**Practices:**
- All component props typed via interfaces
- API responses typed with generics
- Union types for enumerated values
- `type` keyword preferred for imports: `import type { Project }`
- Return types explicit on function declarations where helpful
- No `any` type usage observed

---

*Convention analysis: 2026-02-03*
