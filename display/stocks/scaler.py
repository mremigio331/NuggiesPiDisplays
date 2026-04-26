def downsample(values: list[float], target: int) -> list[float]:
    if not values:
        return []
    if len(values) <= target:
        return values
    bucket_size = len(values) / target
    return [values[int(i * bucket_size)] for i in range(target)]


def normalize(values: list[float], height: int) -> list[int]:
    if not values:
        return []
    lo, hi = min(values), max(values)
    if lo == hi:
        return [height // 2] * len(values)
    return [round((v - lo) / (hi - lo) * (height - 1)) for v in values]
