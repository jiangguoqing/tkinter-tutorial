# Event Loop and Threads

In the button chapter [we used time.sleep in a callback
function](buttons.md#blocking-callback-functions), and it froze
everything. This chapter is all about what happened and why. You'll also
learn to use things like `time.sleep` properly with your tkinter programs.

## Tk's Main Loop

Before we dive into other stuff we need to understand what our
`root.mainloop()` calls at the ends of our programs are doing.

When a tkinter program is running, Tk needs to process different kinds
of events. For example, clicking on a button generates an event, and the
main loop must make the button look like it's pressed down and run our
callback. Tk and most other GUI toolkits do that by simply checking for
any new events over and over again, many times every second. This is
called an **event loop** or **main loop**.

Button callbacks are also ran in the main loop. So if our button
callback takes 5 seconds to run, the main loop can't proess other events
while it's running. For example, it can't close the root window when we
try to close it. That's why everything froze with our `time.sleep(5)`
callback.

## After Callbacks

The `after` method is documented in [after(3tcl)][after(3tcl)], and it's
an easy way to run stuff in Tk's main loop. All widgets have this
method, and it doesn't matter which widget's `after` method you use.
`any_widget.after(milliseconds, callback)` runs `callback()` after
waiting for the given number of milliseconds. The callback runs in Tk's
mainloop, so it must not take a long time to run.

For example, this program displays a simple clock with after callbacks and
[time.asctime](https://docs.python.org/3/library/time.html#time.asctime):

[include]: # (timeout-clock.py)
```python
import tkinter as tk
import time


# this must return soon after starting this
def change_text():
    label['text'] = time.asctime()

    # now we need to run this again after one second, there's no better
    # way to do this than timeout here
    root.after(1000, change_text)


root = tk.Tk()
label = tk.Label(root, text='0')
label.pack()

change_text()      # don't forget to actually start it :)

root.geometry('200x200')
root.mainloop()
```

## Threads

So far we have avoided using functions that take a long time to complete
in tkinter programs, but now we'll do that with [the threading
module](https://docs.python.org/3/library/threading.html). Here's a
minimal example:

[include]: # (printy-threads.py)
```python
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
```

That's pretty cool. The function runs for about a second, but it doesn't
freeze our GUI.

As usual, great power comes with great responsibility. Tkinter isn't
thread-safe, so **we must not do any tkinter stuff in threads**. Don't
do anything like `label['text'] = 'hi'` or even `print(label['text'])`.
It may kind of work for you, but it will make different kinds of weird
problems on some operating systems.

Think about it like this: in tkinter callbacks we can do stuff with
tkinter and we need to return as soon as possible, but in threads we can
do stuff that takes a long time to run but we must not touch tkinter. So
we can use tkinter or run stuff that takes a long time, but not both in
the same place.

### Moving stuff from threads to tkinter

The thread world and tkinter's mainloop world must be separated from
each other, but we can move stuff between them with
[queues](https://docs.python.org/3/library/queue.html). They work like
this:

```python
>>> import queue
>>> the_queue = queue.Queue()
>>> the_queue.put("hello")
>>> the_queue.put("lol")
>>> the_queue.get()
'hello'
>>> the_queue.get()
'lol'
>>> the_queue.get()      # this waits forever, press Ctrl+C to interrupt
Traceback (most recent call last):
  ...
KeyboardInterrupt
>>> the_queue.put('wololo')
>>> the_queue.get(block=False)
'wololo'
>>> the_queue.get(block=False)
Traceback (most recent call last):
  ...
queue.Empty
>>>
```

There are a few things worth noting:

- If you make a variable called `queue`, then you can't use the `queue`
  module. That's why I named it `the_queue` instead.
- Things came out of the queue in the same order that we put them in. We
  put `"hello"` to the queue first, so we also got `"hello"` out of it
  first. If someone talks about a FIFO queue or a First-In-First-Out
  queue, it means this.
- We are not using a list or
  [collections.deque](https://docs.python.org/3/library/collections.html#collections.deque)
  for this. Queues work better with threads.
- If the queue is empty, `some_queue.get()` waits until we put something
  on the queue or we interrupt it. If we pass `block=False` it raises a
  `queue.Empty` exception instead, and never waits for anything.

Usually I need queues for getting stuff from threads back to tkinter.
The thread puts something on the queue, and then an [after
callback](#after-callbacks) gets it from the queue with `block=False`.
Like this:

[include]: # (thread2tk.py)
```python
import queue
import threading
import time
import tkinter as tk

the_queue = queue.Queue()


def thread_target():
    for number in range(10):
        print("thread_target puts hello", number, "to the queue")
        the_queue.put("hello {}".format(number))
        time.sleep(1)

    # let's tell after_callback that this completed
    print('thread_target puts None to the queue')
    the_queue.put(None)


def after_callback():
    try:
        message = the_queue.get(block=False)
    except queue.Empty:
        # let's try again later
        root.after(100, after_callback)
        return

    print('after_callback got', message)
    if message is not None:
        # we're not done yet, let's do something with the message and
        # come back ater
        label['text'] = message
        root.after(100, after_callback)


root = tk.Tk()
label = tk.Label(root)
label.pack()

threading.Thread(target=thread_target).start()
root.after(100, after_callback)

root.geometry('200x200')
root.mainloop()
```

Checking if there's something on the queue every 0.1 seconds may seem a
bit weird, but unfortunately there's no better way to do this. If
checking the queue every 0.1 seconds is too slow for your program, you
can use something like 50 milliseconds instead of 100.

Of course, you can use any other value you want instead of None. For
example, you could add `STOP = object()` to the top of the program, and
then do things like `if message is not STOP`.

### Moving stuff from tkinter to threads

We can also use queues to get things from tkinter to threads. Here we
put stuff to a queue in tkinter and wait for it in the thread, so we
don't need `block=False`. Here's an example:

[include]: # (tk2thread-broken.py)
```python
import queue
import threading
import time
import tkinter as tk

the_queue = queue.Queue()


def thread_target():
    while True:
        message = the_queue.get()
        print("thread_target: doing something with", message, "...")
        time.sleep(1)
        print("thread_target: ready for another message")


def on_click():
    the_queue.put("hello")


root = tk.Tk()
tk.Button(root, text="Click me", command=on_click).pack()
threading.Thread(target=thread_target).start()
root.mainloop()
```

Run the program. You'll notice that it kind of works, but the program
just keeps running when we close the root window. You can interrupt it
with Ctrl+C.

The problem is that Python is waiting for our thread to return, but it's
running a `while True`. To fix that, we need to modify our
`thread_target` to stop when we put None on the queue, and then put a
None to the queue when `root.mainloop` has completed. Like this:

[include]: # (tk2thread.py)
```python
import queue
import threading
import time
import tkinter as tk

the_queue = queue.Queue()


def thread_target():
    while True:
        message = the_queue.get()
        if message is None:
            print("thread_target: got None, exiting...")
            return

        print("thread_target: doing something with", message, "...")
        time.sleep(1)
        print("thread_target: ready for another message")


def on_click():
    the_queue.put("hello")


root = tk.Tk()
tk.Button(root, text="Click me", command=on_click).pack()
threading.Thread(target=thread_target).start()
root.mainloop()

# we get here when the user has closed the window, let's stop the thread
the_queue.put(None)
```

## Summary

- Tk's main loop checks for new events many times every second and does
  something when new events arrive.
- If we tell the main loop to run something like `time.sleep(5)` it
  can't do other things at the same time and everything freezes. Don't
  do that.
- After callbacks tell the main loop to do something after some number
  of milliseconds. You can use them for running something repeatedly by
  calling the after method again in the callback.
- If you need to run something that takes a long time, use threads.
  Don't do tkinter stuff in threads, use queues for moving stuff between
  the mainloop and the thread instead.

[manpage list]: # (start)
[after(3tcl)]: https://www.tcl.tk/man/tcl/TclCmd/after.htm
[manpage list]: # (end)
