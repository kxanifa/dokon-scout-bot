import re

with open(r'c:\Users\Samandar\sherali aka bot\tests\test_stage3.py', 'r', encoding='utf-8') as f:
    content = f.read()

# Replace the assertion
old = "        assert await state.get_state() == StoreFlowStates.waiting_for_location.state"
new = "        # State must NOT advance - photo is now mandatory\n        assert await state.get_state() == StoreFlowStates.waiting_for_photos.state"

if old in content:
    content = content.replace(old, new, 1)  # Only replace first occurrence
    with open(r'c:\Users\Samandar\sherali aka bot\tests\test_stage3.py', 'w', encoding='utf-8') as f:
        f.write(content)
    print("OK - replaced assertion")
else:
    print("NOT FOUND - trying pattern match")
    # Show context
    idx = content.find("test_skip_photos_flow")
    print(content[idx:idx+500])
