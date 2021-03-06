import threading
import time
import tkinter as tk


# in a real program it's best to use after callbacks instead of
# sleeping in a thread, this is just an example
def blocking_function():
    print("blocking function starts")
    time.sleep(1)
    print("blocking function ends")


def start_new_thread():
    thread = threading.Thread(target=blocking_function)
    thread.start()


root = tk.Tk()
button = tk.Button(root, text="Start the blocking function",
                   command=start_new_thread)
button.pack()
root.mainloop()
