import sys
import os
import csp
import stat
import threading
import argparse
from pipe_utils import nonblocking_opener, SelectorReader, LineBuffer

import matplotlib
import matplotlib.pyplot as plt
import matplotlib.lines
import numpy as np

#matplotlib.use("TkAgg")

sel = SelectorReader()

parser = argparse.ArgumentParser()
parser.add_argument('files', action='store', default='-', nargs='*', type=str)
parser.add_argument('--follow-width', type=float)
parser.add_argument('-u', '--unit', default=1.0, type=float)
parser.add_argument('--xlabel', type=str)
parser.add_argument('--ylabel', type=str)
parser.add_argument('--label', action='append', default=[], type=str)
args = parser.parse_args()

pipes = []
for name in args.files:
    if name == '-':
        pipes.append(sys.stdin.buffer.raw)
    else:
        pipes.append(open(name, 'br', buffering=0, opener=nonblocking_opener))

line_buffer = dict()
stale = set()

for file in pipes:
    try:
        sel.register(file)
        lb = LineBuffer()
    except PermissionError: # possibly not fifo
        print("failed to register epoll", file=sys.stderr)
        lb = LineBuffer(file.read().decode('utf-8'))
        stale.add(file)

    line_buffer[file] = lb

shutdown = False
def send_shutdown():
    global shutdown
    shutdown = True

def translate_label(label):
    for s in args.label:
        a, b = s.split(';')
        if label == a:
            return b
    return label

fig, ax = plt.subplots()
fig.canvas.mpl_connect('close_event', lambda event: send_shutdown())
plt.show(block=False)
waiting_for_input = True
lock = threading.Lock()

if args.xlabel:
    ax.set_xlabel(args.xlabel)

if args.ylabel:
    ax.set_ylabel(args.ylabel)

def read_input(lock, sel, stale, line_buffer):
    print("start input thread")
    while len(sel) > 0:
        if shutdown:
            break
        for f in sel.select(timeout=0.1):
            if b := f.read(1024): # read 1024 bytes at max per file
                s = b.decode('utf-8')
                with lock:
                    line_buffer[f].write(s)
                    stale.add(f)
            else:
                sel.unregister(f)
                f.close()
                stale.add(f)
                print(f"closed file {f}")
    global waiting_for_input
    waiting_for_input = False
    sel.close()
    print("end of input")

input_reader_thread = threading.Thread(target=lambda: read_input(lock, sel, stale, line_buffer))
input_reader_thread.start()

plots = dict()

while waiting_for_input or stale:

    with lock:
        if len(stale) > 0:
            for f in stale:
                while line_buffer[f].num_lines() > 0:
                    data, meta = csp.parse(line_buffer[f].readline())
                    for t, v in data.items():
                        na = False
                        if v == '':
                            continue
                        elif v == '-':
                            na = True
                        else:
                            try:
                                y = float(v)
                            except:
                                print('could not interpret value "{}"'.format(v), file=sys.stderr)
                                continue

                        if type(t) == int:
                            t = "#" + str(t)

                        plid = f.name + ':' + t
                        if plid in plots:
                            plot = plots[plid]
                            mpl_line = plot['mpl_line']
                        else:
                            mpl_line = ax.add_line(matplotlib.lines.Line2D([], [], drawstyle='default'))
                            mpl_line.set_color(np.random.rand(3,))
                            mpl_line.set_label(translate_label(plid))
                            plot = { 'mpl_line': mpl_line, 'x_next': 0 }
                            plots[plid] = plot

                        if not na:
                            xs, ys = mpl_line.get_xdata(), mpl_line.get_ydata()
                            xs = np.append(xs, plot['x_next'])
                            ys = np.append(ys, y)
                            mpl_line.set_data(xs, ys)
                        plot['x_next'] += args.unit

    if len(plots) > 0:
        ax.legend(prop={'family': 'IPAexGothic'})
        ax.relim()
        if args.follow_width:
            x_max = max(map(lambda plot: max(plot['mpl_line'].get_xdata()), plots.values()))
            x_left = (x_max - args.follow_width) if x_max > args.follow_width else 0
            ax.set_xlim(x_left, x_max)
        ax.autoscale_view()

    clear_stale = set()
    for f in stale:
        if line_buffer[f].num_lines() == 0:
            clear_stale.add(f)
    stale -= clear_stale
    
    fig.canvas.draw_idle()
    fig.canvas.flush_events()

plt.show()

print("exiting")

