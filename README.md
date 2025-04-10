# askin
### Asynchronous Keyboard Input

`askin` is a Python package that provides a simple way to get keyboard input asynchronously.

### Installation

```bash
pip install askin
```

### Usage

```python
from askin import KeyboardController

class KeyState:
    def __init__(self):
        self.value = 0
    async def update(self, key: str):
        if key == "a":
            self.value += 1
        elif key == "b":
            self.value -= 1

async def key_handler(key: str):
    key_state.update(key)

async def main():
    key_state = KeyState()
    controller = KeyboardController(key_handler=key_state.update, timeout=0.001)
    await controller.start()

    try:
        while True:
            print(key_state.value)
            await asyncio.sleep(0.1)
    finally:
        await controller.stop()


if __name__ == "__main__":
    asyncio.run(main())
``` 





