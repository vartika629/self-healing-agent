# Demo 6: logic bug - no crash at first, but the assert check fails.
def percentage(obtained, total):
    return obtained / total * 10

result = percentage(45, 50)
print("Percentage:", result)
assert result == 90, f"Expected 90 but got {result}"
print("All checks passed!")
