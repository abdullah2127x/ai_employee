import threading
import time

def watcher():
    while True:
        print("Watching...")
        time.sleep(1)

t = threading.Thread(target=watcher, daemon=True)

t.start()

time.sleep(3)
# print("Main program ends")
# watcher()