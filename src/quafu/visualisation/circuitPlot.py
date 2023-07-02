import numpy as np
import quafu
import matplotlib.patheffects as pe
import matplotlib.pyplot as plt
from matplotlib.collections import PolyCollection, PatchCollection, LineCollection
from matplotlib.patches import Circle, Arc
from matplotlib.text import Text

line_args = {}
box_args = {}

DEEPCOLOR = '#0C161F'
BLUE = '#1f77b4'
ORANGE = '#ff7f0e'
GREEN = '#2ca02c'
GOLDEN = '#FFB240'
GARNET = '#C0392B'

"""
layers(zorder):

0: figure
1: bkg box
2: wires
3: closed patches
4: white bkg for label/text
5: labels
"""

su2_gate_names = ['x', 'y', 'z', 'id', 'w',
                  'h', 't', 'tdg', 's', 'sdg', 'sx', 'sy', 'sw',
                  'phase',
                  'rx', 'ry', 'rz',
                  ]

swap_gate_names = ['swap', 'iswap']
r2_gate_names = ['rxx', 'ryy', 'rzz']
c2_gate_names = ['cp', 'cs', 'ct', 'cx', 'cy', 'cz']
c3_gate_names = ['fredkin', 'toffoli']
cm_gate_names = ['mcx', 'mcy', 'mcz']
operation_names = ['barrier', 'delay']


class CircuitPlotManager:
    """
    A class to manage the plotting of quantum circuits.
    Stores style parameters and provides functions to plot.

    To be initialized when circuit.plot() is called.
    """
    _wire_color = '#FF0000'
    _wire_lw = 1.5

    _light_blue = '#3B82F6'
    _ec = DEEPCOLOR

    _a_inch = 2 / 2.54  # physical lattice constant in inch
    _a = 0.5  # box width and height, unit: ax

    _barrier_width = _a / 3  # barrier width

    _stroke = pe.withStroke(linewidth=2, foreground='white')

    def __init__(self, qc: quafu.QuantumCircuit):
        """
        Processing graphical info from a quantum circuit,
        whose gates are stored as a list at present.

        In the future the circuit will be stored as a graph
        or graph-like object, procedure will be much simplified.
        (TODO)
        """
        self.qbit_num = qc.num

        # step0: containers of graphical elements

        self._h_wire_points = []
        self._ctrl_wire_points = []

        self._closed_patches = []

        self._mea_arc_patches = []
        self._mea_point_patches = []

        self._ctrl_points = []
        self._not_points = []
        self._swap_points = []

        self._barrier_points = []

        self._text_list = []

        # step1: process gates/instructions
        dorders = np.zeros(qc.num, dtype=int)
        for gate in qc.gates:
            id_name = gate.name.lower()
            _which = slice(np.min(gate.pos), np.max(gate.pos) + 1)
            depth = np.max(dorders[_which])
            paras = getattr(gate, 'paras', None)

            # TODO: call processing functions
            if id_name == 'barrier':
                self._proc_barrier(depth, gate.pos)
            elif id_name == 'measure':
                self._proc_measure(depth, gate.pos)
            elif id_name in su2_gate_names:
                self._proc_su2(id_name, depth, gate.pos, paras)
            elif id_name == 'swap':
                self._proc_swap(depth, gate.pos)
            elif id_name == 'cx':
                self._proc_ctrl(depth, gate.ctrls[0], gate.targs[0], 'x')
            else:
                # control
                raise NotImplemented
            dorders[_which] = depth + 1
        self.depth = np.max(dorders) + 1

        for q, c in qc.measures.items():
            self._proc_measure(self.depth - 1, q)

        # step2: initialize bit-label
        self.q_label = [f'q_{i}' for i in range(qc.num)]
        self.c_label = [f'c_{i}' for i in qc.measures.values()]

        # step3: figure coordination
        self.xs = np.arange(-3 / 2, self.depth + 3 / 2)
        self.ys = np.arange(-2, self.qbit_num + 1 / 2)

    def __call__(self,
                 title=None, *args, **kwargs):
        """

        """
        # Not supported by patch collections?
        # if 'xkcd' in kwargs:
        #     import random
        #     plt.gca().xkcd(randomness=random.randint(0, 1000))
        if title is not None:
            title = Text((self.xs[0] + self.xs[-1]) / 2, -0.8,
                         title,
                         size=30,
                         ha='center', va='baseline')
            self._text_list.append(title)

        # initialize a figure
        _size_x = self._a_inch * abs(self.xs[-1] - self.xs[0])
        _size_y = self._a_inch * abs(self.ys[-1] - self.ys[0])
        fig = plt.figure(figsize=(_size_x, _size_y))  # inch
        ax = fig.add_axes([0, 0, 1, 1],
                          aspect=1,
                          xlim=[self.xs[0], self.xs[-1]],
                          ylim=[self.ys[0], self.ys[-1]],
                          )
        ax.axis('off')
        ax.invert_yaxis()

        self._circuit_wires()
        self._inits_label()
        self._measured_label()
        self._render_circuit()

    #########################################################################
    # Helper functions for processing gates/instructions into graphical
    # elements. Add only points data of for the following collection-wise
    # plotting if possible, create a patch otherwise.
    #########################################################################
    def _circuit_wires(self):
        """
        plot horizontal circuit wires
        """
        for y in range(self.qbit_num):
            x0 = self.xs[0] + 1
            x1 = self.xs[-1] - 1
            self._h_wire_points.append([[x0, y], [x1, y]])

    def _gate_bbox(self, x, y, fc: str):
        a = self._a
        from matplotlib.patches import FancyBboxPatch
        bbox = FancyBboxPatch((-a / 2 + x, -a / 2 + y), a, a,
                              boxstyle=f'round, pad={0.2 * a}',
                              edgecolor=DEEPCOLOR,
                              facecolor=fc,
                              )
        self._closed_patches.append(bbox)

    def _inits_label(self, labels: list[int] = None):
        """ qubit-labeling """
        if labels is None:
            labels = self.q_label

        for i, label in enumerate(labels):
            label = r'$|%s\rangle$' % label
            txt = Text(-2 / 3, i,
                       label,
                       size=18,
                       color=DEEPCOLOR,
                       ha='right',
                       va='center',
                       )
            self._text_list.append(txt)

    def _measured_label(self, labels: list[int] = None):
        """ measured qubit-labeling """
        if labels is None:
            labels = self.c_label

        for i, label in enumerate(labels):
            label = r'$%s$' % label
            txt = Text(self.xs[-1] - 3 / 4, i,
                       label,
                       size=18,
                       color=DEEPCOLOR,
                       ha='left',
                       va='center',
                       )
            self._text_list.append(txt)

    def _gate_label(self, s, x, y):
        if not s:
            return None
        _dy = 0.05
        text = Text(x, y + _dy,
                    s,
                    size=24,
                    color=DEEPCOLOR,
                    ha='center',
                    va='center',
                    )
        text.set_path_effects([self._stroke])
        self._text_list.append(text)

    def _para_label(self, para_txt, x, y):
        """ label parameters """
        if not para_txt:
            return None
        _dx = 0
        text = Text(x + _dx, y+0.7*self._a,
                    para_txt,
                    size=12,
                    color=DEEPCOLOR,
                    ha='center',
                    va='top',
                    )
        self._text_list.append(text)

    def _measure_label(self, x, y):
        from matplotlib.patches import FancyArrow
        a = self._a
        r = 1.1 * a
        d = 1.2 * a / 3.5

        arrow = FancyArrow(x=x,
                           y=y + d,
                           dx=0.15,
                           dy=-0.35,
                           width=0.04,
                           facecolor=DEEPCOLOR,
                           head_width=0.07,
                           head_length=0.15,
                           edgecolor='white')
        arc = Arc((x, y + d),
                  width=r,
                  height=r,
                  lw=1,
                  theta1=180,
                  theta2=0,
                  fill=False,
                  zorder=4,
                  color=DEEPCOLOR,
                  capstyle='round',
                  )
        center_bkg = Circle((x, y + d),
                            radius=0.035,
                            color='white',
                            )
        center = Circle((x, y + d),
                        radius=0.025,
                        facecolor=DEEPCOLOR,
                        )
        self._mea_arc_patches.append(arc)
        self._mea_point_patches += [center_bkg, arrow, center]

    #########################################################################
    # # # # processing-functions: decompose ins into graphical elements # # #
    #########################################################################
    def _proc_su2(self, id_name, depth, pos, paras):
        if id_name in ['x', 'y', 'z', 'h', 'id', 's', 't', 'p', 'u']:
            fc = '#EE7057'
            label = id_name.capitalize()
        elif id_name in ['rx', 'ry', 'rz']:
            fc = '#6366F1'
            label = id_name.upper()
        else:
            fc = '#8C9197'
            label = '?'

        if id_name in ['rx', 'ry', 'rz', 'p']:
            para_txt = r'$\theta=$' + f'{paras:.3f}'
        else:
            para_txt = None

        self._gate_label(label, depth, pos)
        self._para_label(para_txt, depth, pos)
        self._gate_bbox(depth, pos, fc)

    def _proc_ctrl(self, depth, ctrl_pos, tar_pos, tar_name, ctrl_type: bool = True):
        if tar_name == 'x':
            self._ctrl_points.append((depth, ctrl_pos, ctrl_type))
            self._ctrl_wire_points.append([[depth, ctrl_pos], [depth, tar_pos]])
            self._not_points.append((depth, tar_pos))
        else:
            raise NotImplemented

    def _proc_swap(self, depth, pos):
        p1, p2 = pos
        self._swap_points += [[depth, p] for p in pos]
        self._ctrl_wire_points.append([[depth, p1], [depth, p2]])

    def _proc_barrier(self, depth, pos: list):
        x0 = depth - self._barrier_width
        x1 = depth + self._barrier_width

        for p in pos:
            y0 = (p - 1 / 2)
            y1 = (p + 1 / 2)
            nodes = [[x0, y0], [x0, y1], [x1, y1], [x1, y0], [x0, y0]]
            self._barrier_points.append(nodes)

    def _proc_measure(self, depth, pos):
        fc = GOLDEN
        self._gate_bbox(depth, pos, fc)
        self._measure_label(depth, pos)

        # TODO: decide whether to draw double wire for measurement
        # y = pos + 0.02
        # x0 = depth
        # x1 = self.depth - 1 / 2
        # self._h_wire_points.append([[x0, y], [x1, y]])

    #########################################################################
    # # # # # # # # # # # # # # rendering functions # # # # # # # # # # # # #
    #########################################################################
    def _render_h_wires(self):
        h_lines = LineCollection(self._h_wire_points,
                                 zorder=0,
                                 colors=self._wire_color,
                                 alpha=0.8,
                                 linewidths=2,
                                 )
        plt.gca().add_collection(h_lines)

    def _render_ctrl_wires(self):
        v_lines = LineCollection(self._ctrl_wire_points,
                                 zorder=0,
                                 colors=self._light_blue,
                                 alpha=0.8,
                                 linewidths=4,
                                 )
        plt.gca().add_collection(v_lines)

    def _render_closed_patch(self):
        collection = PatchCollection(self._closed_patches,
                                     match_original=True,
                                     zorder=3,
                                     ec=self._ec,
                                     linewidths=0.5,
                                     )
        plt.gca().add_collection(collection)

    def _render_ctrl_nodes(self):
        circle_collection = []
        r = self._a / 4
        for x, y, ctrl in self._ctrl_points:
            fc = '#3B82F6' if ctrl else 'white'
            circle = Circle((x, y), radius=r, fc=fc)
            circle_collection.append(circle)
        circles = PatchCollection(circle_collection,
                                  match_original=True,
                                  zorder=5,
                                  ec=self._ec,
                                  linewidths=2,
                                  )
        plt.gca().add_collection(circles)

    def _render_not_nodes(self):
        points = []
        rp = self._a * 0.3
        r = self._a * 0.5

        for x, y in self._not_points:
            points.append([[x, y - rp], [x, y + rp]])
            points.append([[x - rp, y], [x + rp, y]])
            circle = Circle((x, y), radius=r, lw=1,
                            fc='#3B82F6')
            self._closed_patches.append(circle)

        collection = LineCollection(points,
                                    zorder=5,
                                    colors='white',
                                    linewidths=2,
                                    capstyle='round',
                                    )
        plt.gca().add_collection(collection)

    def _render_swap_nodes(self):
        points = []
        r = self._a / (4 ** (1 / 2))
        for x, y in self._swap_points:
            points.append([[x - r, y - r], [x + r, y + r]])
            points.append([[x + r, y - r], [x - r, y + r]])
        collection = LineCollection(points,
                                    zorder=5,
                                    colors='#3B82F6',
                                    linewidths=4,
                                    capstyle='round',
                                    )
        plt.gca().add_collection(collection)

    def _render_measure(self):
        stroke = pe.withStroke(linewidth=4, foreground='white')
        arcs = PatchCollection(self._mea_arc_patches,
                               match_original=True,
                               capstyle='round',
                               zorder=4)
        arcs.set_path_effects([stroke])

        plt.gca().add_collection(arcs)
        pointers = PatchCollection(self._mea_point_patches,  # note the order
                                   match_original=True,
                                   zorder=5,
                                   facecolors=DEEPCOLOR,
                                   linewidths=2,
                                   )
        plt.gca().add_collection(pointers)

    def _render_barrier(self):
        barrier = PolyCollection(self._barrier_points,
                                 closed=True,
                                 fc='lightgray',
                                 hatch='///',
                                 zorder=4)
        plt.gca().add_collection(barrier)

    def _render_txt(self):
        for txt in self._text_list:
            plt.gca().add_artist(txt)

    def _render_circuit(self):
        self._render_h_wires()
        self._render_ctrl_wires()
        self._render_ctrl_nodes()
        self._render_not_nodes()

        self._render_swap_nodes()
        self._render_measure()
        self._render_barrier()
        self._render_closed_patch()
        self._render_txt()


if __name__ == '__main__':
    n = 8
    qc_ = quafu.QuantumCircuit(n)
    qc_.h(0)

    qc_.barrier([0, 3])
    qc_.x(0)
    qc_.swap(0, 4)
    qc_.cnot(3, 6)
    qc_.rz(4, 3.2)

    for k in range(10):
        qc_.x(7)
    for k in range(n-1):
        qc_.cnot(k, k + 1)
    qc_.measure([0, 1, 2, 3], [0, 1, 2, 3])

    # for i in range(30):
    #     qc.x(4)

    cmp = CircuitPlotManager(qc_)
    cmp(title='This Is a Quantum Circuit')
    import os
    if not os.path.exists('./figures/'):
        os.mkdir('./figures/')
    plt.savefig('./figures/test.png', dpi=300, transparent=True)
    plt.close()
    # plt.show()