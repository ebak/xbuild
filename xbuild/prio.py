
def prioCmp(a, b):
    chkLen = min(len(a), len(b))
    for i in range(chkLen):
        diff = b[i] - a[i]  # reverse compare to achieve high on top in SortedList
        if diff:
            return diff
    return 0
