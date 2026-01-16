# CSS Class Mapping Notes

## Overview
This document maps Bootstrap-style component classes to the actual Tailwind CSS classes used in the SDLC Orchestrator templates. This mapping is essential for creating accurate CSS validation tests.

## Templates Analyzed
- `base.html`
- `dashboard.html`
- `plans.html`
- `plan_detail.html`
- `runs.html`
- `run_detail.html`

---

## Form Inputs

### Text Input (form-control equivalent)
**Bootstrap:** `form-control`
**Tailwind in templates:**
```
flex-1 px-4 py-2 border border-gray-300 rounded-md shadow-sm focus:outline-none focus:ring-2 focus:ring-blue-500 focus:border-blue-500 sm:text-sm
```

**Location:** `dashboard.html` line 111-113
```html
<input type="text" id="plan-description" name="description"
       class="flex-1 px-4 py-2 border border-gray-300 rounded-md shadow-sm focus:outline-none focus:ring-2 focus:ring-blue-500 focus:border-blue-500 sm:text-sm"
       placeholder="Enter feature description (e.g., Add user authentication)">
```

**Key identifying classes:**
- `border` or `border-gray-300` - Border styling
- `rounded-md` - Border radius
- `px-4 py-2` - Padding
- `focus:ring-2` - Focus state ring
- `focus:border-blue-500` - Focus border color

---

## Buttons

### Primary Button (btn btn-primary equivalent)
**Bootstrap:** `btn btn-primary`
**Tailwind in templates:**
```
inline-flex items-center px-4 py-2 border border-transparent text-sm font-medium rounded-md shadow-sm text-white bg-blue-600 hover:bg-blue-700
```

**Locations:**
- `dashboard.html` line 115-117 (Create Plan button)
- `plan_detail.html` line 30 (Start Build button)
- `runs.html` line 72 (Go to Dashboard button)
- `plans.html` line 131 (Go to Dashboard button)

**Key identifying classes:**
- `bg-blue-600` - Primary blue background
- `hover:bg-blue-700` - Hover state
- `text-white` - White text
- `rounded-md` - Border radius
- `px-4 py-2` - Standard padding

### Secondary/Outline Button (btn btn-secondary/btn-outline equivalent)
**Bootstrap:** `btn btn-secondary` or `btn-outline`
**Tailwind in templates:**
```
inline-flex items-center px-4 py-2 border border-gray-300 text-sm font-medium rounded-md text-gray-700 bg-white hover:bg-gray-50
```

**Locations:**
- `plan_detail.html` line 47 (Back to Plans)
- `run_detail.html` line 121 (Back to Runs)

**Key identifying classes:**
- `bg-white` - White background
- `border-gray-300` - Gray border
- `text-gray-700` - Gray text
- `hover:bg-gray-50` - Light hover state

### Purple/Review Button (btn btn-purple equivalent)
**Bootstrap:** N/A (custom)
**Tailwind in templates:**
```
inline-flex items-center px-4 py-2 border border-transparent text-sm font-medium rounded-md shadow-sm text-white bg-purple-600 hover:bg-purple-700
```

**Location:** `plan_detail.html` line 40 (Start Review button)

**Key identifying classes:**
- `bg-purple-600` - Purple background
- `hover:bg-purple-700` - Darker purple on hover

### Small Link Button
**Tailwind in templates:**
```
inline-flex items-center px-3 py-1.5 text-xs font-medium text-blue-700 bg-blue-100 rounded-md hover:bg-blue-200 transition-colors
```

**Location:** `plans.html` line 110 (View Full Plan link)

---

## Status Badges

### Status Badge (General)
**Bootstrap:** `badge`
**Tailwind in templates:**
```
inline-flex items-center px-3 py-1 rounded-full text-sm font-medium
```

**Variations by status:**
- **Completed/Success:** `bg-green-100 text-green-800`
- **Pending/Warning:** `bg-yellow-100 text-yellow-800`
- **Running/In-Progress/Info:** `bg-blue-100 text-blue-800`
- **Failed/Error:** `bg-red-100 text-red-800`

**Locations:**
- `plan_detail.html` line 15-19
- `run_detail.html` line 14-18
- `runs.html` line 29-33
- `dashboard.html` line 138-142, 173-177
- `plans.html` line 41-45

### Small Status Badge
**Tailwind in templates:**
```
px-2 inline-flex text-xs leading-5 font-semibold rounded-full
```

**With status colors as above**

---

## Cards/Panels

### Card Container (card equivalent)
**Bootstrap:** `card`
**Tailwind in templates:**
```
bg-white shadow overflow-hidden sm:rounded-lg
```
or
```
bg-white shadow rounded-lg
```

**Locations:** All templates

### Card Header
**Tailwind in templates:**
```
px-4 py-5 sm:px-6
```

### Card with Definition List
**Tailwind in templates:**
```html
<div class="bg-white shadow overflow-hidden sm:rounded-lg">
    <div class="px-4 py-5 sm:px-6">
        <h3 class="text-lg font-medium text-gray-900">Title</h3>
    </div>
    <div class="border-t border-gray-200">
        <dl>...</dl>
    </div>
</div>
```

---

## Form Groups

### Form Group Container
**Bootstrap:** `form-group`
**Tailwind in templates:** Not explicitly defined; forms use:
```
flex gap-4
```
or
```
grid grid-cols-1 gap-6 lg:grid-cols-2
```

**Location:** `dashboard.html` line 110

---

## Progress Bars

### Progress Bar Container
**Bootstrap:** `progress`
**Tailwind in templates:**
```
w-full bg-gray-200 rounded-full h-2
```
or
```
w-full bg-gray-200 rounded-full h-3
```

### Progress Bar Fill
**Bootstrap:** `progress-bar`
**Tailwind in templates:**
```
bg-blue-600 h-2 rounded-full transition-all duration-300
```
or
```
bg-blue-600 h-3 rounded-full transition-all duration-300
```

**Locations:**
- `runs.html` line 54-55
- `run_detail.html` line 79-80
- `dashboard.html` line 182-183

---

## Lists

### List Container
**Bootstrap:** `list-group`
**Tailwind in templates:**
```
divide-y divide-gray-200
```

### List Item
**Bootstrap:** `list-group-item`
**Tailwind in templates:**
```
py-3
```
or interactive:
```
block hover:bg-gray-50
```

---

## Navigation

### Nav Link
**Bootstrap:** `nav-link`
**Tailwind in templates:**
```
border-transparent text-gray-500 hover:border-gray-300 hover:text-gray-700 inline-flex items-center px-1 pt-1 border-b-2 text-sm font-medium
```

**Location:** `base.html` lines 114-122

---

## Summary Table for Test Implementation

| Component Type | Bootstrap Class | Key Tailwind Classes to Test |
|---------------|-----------------|------------------------------|
| Text Input | `form-control` | `border`, `rounded-md`, `px-4`, `py-2`, `focus:ring` |
| Primary Button | `btn btn-primary` | `bg-blue-600`, `text-white`, `rounded-md`, `hover:bg-blue-700` |
| Secondary Button | `btn btn-secondary` | `bg-white`, `border-gray-300`, `text-gray-700` |
| Status Badge | `badge` | `rounded-full`, `font-medium`, `bg-{color}-100`, `text-{color}-800` |
| Card | `card` | `bg-white`, `shadow`, `rounded-lg` |
| Progress Bar | `progress` | `bg-gray-200`, `rounded-full`, `h-2` or `h-3` |
| Progress Fill | `progress-bar` | `bg-blue-600`, `rounded-full` |
| List | `list-group` | `divide-y`, `divide-gray-200` |

---

## Notes for Test Implementation

1. **No traditional form-control class:** The templates don't use a single "form-control" class. Instead, inputs have multiple utility classes. Tests should check for the presence of key styling classes like `border`, `rounded-md`, and `focus:ring`.

2. **Button identification:** Primary buttons are identified by `bg-blue-600`, secondary by `bg-white` with `border-gray-300`.

3. **Status-based styling:** Many elements use conditional Tailwind classes based on status (completed, pending, running, failed). Tests should verify correct color classes are applied.

4. **Only one form input exists:** The entire application has only ONE text input field - the plan description input in `dashboard.html`. This is the only `<input>` element in all templates.

5. **Buttons are either `<button>` or `<a>` tags:** Action buttons use `<button>` elements, navigation links styled as buttons use `<a>` tags.

---

## Exact Class Strings for Test Assertions

### Form Input Classes (Exact)
```python
FORM_INPUT_CLASSES = [
    "flex-1",
    "px-4",
    "py-2",
    "border",
    "border-gray-300",
    "rounded-md",
    "shadow-sm",
    "focus:outline-none",
    "focus:ring-2",
    "focus:ring-blue-500",
    "focus:border-blue-500",
    "sm:text-sm"
]
```

### Primary Button Classes (Exact)
```python
PRIMARY_BUTTON_CLASSES = [
    "inline-flex",
    "items-center",
    "px-4",
    "py-2",
    "border",
    "border-transparent",
    "text-sm",
    "font-medium",
    "rounded-md",
    "shadow-sm",
    "text-white",
    "bg-blue-600",
    "hover:bg-blue-700",
    "focus:outline-none",
    "focus:ring-2",
    "focus:ring-offset-2",
    "focus:ring-blue-500"
]
```

### Secondary Button Classes (Exact)
```python
SECONDARY_BUTTON_CLASSES = [
    "inline-flex",
    "items-center",
    "px-4",
    "py-2",
    "border",
    "border-gray-300",
    "text-sm",
    "font-medium",
    "rounded-md",
    "text-gray-700",
    "bg-white",
    "hover:bg-gray-50"
]
```

### Status Badge Base Classes
```python
STATUS_BADGE_BASE = [
    "inline-flex",
    "items-center",
    "rounded-full",
    "font-medium"  # or font-semibold for small badges
]

STATUS_BADGE_COLORS = {
    "completed": ["bg-green-100", "text-green-800"],
    "pending": ["bg-yellow-100", "text-yellow-800"],
    "running": ["bg-blue-100", "text-blue-800"],
    "in-progress": ["bg-blue-100", "text-blue-800"],
    "failed": ["bg-red-100", "text-red-800"],
    "error": ["bg-red-100", "text-red-800"]
}
```

### Progress Bar Classes
```python
PROGRESS_CONTAINER_CLASSES = [
    "w-full",
    "bg-gray-200",
    "rounded-full"
    # h-2 or h-3 depending on context
]

PROGRESS_FILL_CLASSES = [
    "bg-blue-600",
    "rounded-full"
    # h-2 or h-3 depending on context
]
```

### Card Container Classes
```python
CARD_CLASSES = [
    "bg-white",
    "shadow",
    # rounded-lg or sm:rounded-lg
]
```
