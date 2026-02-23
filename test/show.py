#!/usr/bin/env python
# need an environment that has matplotlib [and optionally wat]
# nsd-conda-wrap.sh quicknxs --classic show.py [path-to-pkl-file]

import sys

import numpy as np
import matplotlib.pyplot as plt
import pickle

try:
    import wat  # https://github.com/igrek51/wat
except ModuleNotFoundError as e:
    print('duck-typing wat module, see https://github.com/igrek51/wat')
    class _wat(object):
        @classmethod
        def __div__(self, _other):
            return None
        def __truediv__(self, _other):
            return None
    wat = _wat()

filename = sys.argv[1] if len(sys.argv) > 1 else '/SNS/users/6ov/shared/REF_M/13720/session7-oss/REF_M_43050_peak1_OffSpec_On_Off.pkl'

# https://github.com/matplotlib/matplotlib/issues/10843
plt.ioff()

# https://share.google/aimode/7I0bb8CfAO8qyGyJ4
def show_figure(fig):
    """Create a dummy figure and use its manager to display 'fig'"""
    dummy = plt.figure()
    new_manager = dummy.canvas.manager
    new_manager.canvas.figure = fig
    fig.set_canvas(new_manager.canvas)
    plt.show()

if filename.endswith('.npz'):
    npz = np.load(filename, allow_pickle=True)
    print('***npz:***')
    wat / npz
    #print('***ax:***')
    #wat / npz['ax']
    #print('***data_to_save:***')
    #wat / npz['data_to_save']
    #print('***canvas_figure:***')
    #wat / npz['canvas_figure']
    #print('***ax_lines:***')
    #wat / npz['ax_lines']
    print('***ax_figure:***')
    wat / npz['ax_figure']

    fig = npz['ax_figure'].T
    print(f'figure.shape={fig.shape}')

else:
    with open(filename, 'rb') as f:
        pkl = pickle.load(f)
    print('***pkl:***')
    wat / pkl

    # b/c pickle.dump((ax, data_to_save, self.canvas.figure), fp, protocol=4)
    fig = pkl[2]
    print('***fig:***')
    wat / fig

## try 1
#plt.figure()
#plt.imshow(fig)

## https://share.google/aimode/TdaWN7EexCsY7JP3O
#ax = fig.axes[0]
#ax.grid(True)
#plt.show()

# https://stackoverflow.com/questions/35649603/pickle-figures-from-matplotlib
#fig.show()

# https://share.google/aimode/7I0bb8CfAO8qyGyJ4
show_figure(fig)
