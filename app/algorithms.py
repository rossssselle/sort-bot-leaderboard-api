from typing import Callable

def bubble_sort(arr: list[int]) -> list[int]:
    a = arr.copy()
    n = len(a)
    for i in range(n):
        for j in range(0, n - i - 1):
            if a[j] > a[j + 1]:
                a[j], a[j + 1] = a[j + 1], a[j]
    return a


def insertion_sort(arr: list[int]) -> list[int]:
    a = arr.copy()
    for i in range(1, len(a)):
        key = a[i]
        j = i - 1
        while j >= 0 and a[j] > key:
            a[j + 1] = a[j]
            j -= 1
        a[j + 1] = key
    return a


def merge_sort(arr: list[int]) -> list[int]:
    a = list(arr)
    n = len(a)
    width = 1
    while width < n:
        for i in range(0, n, 2 * width):
            left = a[i : i + width]
            right = a[i + width : i + 2 * width]
            merged = _merge(left, right)
            a[i : i + len(merged)] = merged
        width *= 2
    return a


def _merge(left: list[int], right: list[int]) -> list[int]:
    result = []
    i = j = 0
    while i < len(left) and j < len(right):
        if left[i] <= right[j]:
            result.append(left[i])
            i += 1
        else:
            result.append(right[j])
            j += 1
    result.extend(left[i:])
    result.extend(right[j:])
    return result


def quicksort(arr: list[int]) -> list[int]:
    a = list(arr)
    if len(a) <= 1:
        return a
    stack = [(0, len(a) - 1)]
    while stack:
        lo, hi = stack.pop()
        if lo >= hi:
            continue
        pivot = a[(lo + hi) // 2]
        i, j = lo, hi
        while i <= j:
            while a[i] < pivot:
                i += 1
            while a[j] > pivot:
                j -= 1
            if i <= j:
                a[i], a[j] = a[j], a[i]
                i += 1
                j -= 1
        if lo < j:
            stack.append((lo, j))
        if i < hi:
            stack.append((i, hi))
    return a


def heap_sort(arr: list[int]) -> list[int]:
    import heapq
    return list(heapq.nsmallest(len(arr), arr))


def python_builtin(arr: list[int]) -> list[int]:
    return sorted(arr)

# A deliberately bad algorithm that just sleeps forever, to test timeout handling
def sleep_sort(arr: list[int]) -> list[int]:
    import time
    time.sleep(9999)
    return sorted(arr)


SortFunction = Callable[[list[int]], list[int]]

ALGORITHM_REGISTRY: dict[str, dict] = {
    "bubble_sort": {
        "fn": bubble_sort,
        "description": "O(n²) — simple comparison sort, swaps adjacent elements.",
    },
    "insertion_sort": {
        "fn": insertion_sort,
        "description": "O(n²) average — fast on nearly-sorted data.",
    },
    "merge_sort": {
        "fn": merge_sort,
        "description": "O(n log n) — divide-and-conquer, stable, consistent performance.",
    },
    "quicksort": {
        "fn": quicksort,
        "description": "O(n log n) average — fast in practice, O(n²) worst case.",
    },
    "heap_sort": {
        "fn": heap_sort,
        "description": "O(n log n) — selection-based, uses a binary heap.",
    },
    "python_builtin": {
        "fn": python_builtin,
        "description": "Python's Timsort — hybrid merge/insertion sort, highly optimized.",
    },
    "sleep_sort": {
        "fn": sleep_sort,
        "description": "Intentionally hangs forever — for testing timeout handling.",
    },
}


def get_sort_function(algorithm: str) -> SortFunction:
    if algorithm not in ALGORITHM_REGISTRY:
        available = ", ".join(ALGORITHM_REGISTRY.keys())
        raise KeyError(
            f"Unknown algorithm '{algorithm}'. Available: {available}"
        )
    return ALGORITHM_REGISTRY[algorithm]["fn"]