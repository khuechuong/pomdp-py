"""
Utility functions making it easier to debug POMDP planning.
"""
import sys
from pomdp_py.algorithms.po_uct import TreeNode, QNode, VNode, RootVNode
from pomdp_py.utils import typ, similar, special_char

SIMILAR_THRESH = 0.6
MARKED = set()  # tracks marked nodes on tree

def sorted_by_str(enumerable):
    return sorted(enumerable, key=lambda n: str(n))

def _node_pp(node, e=None, p=None):
    # We want to return the node, but we don't want to print it on pdb with
    # its default string. But instead, we want to print it with our own
    # string formatting.
    if isinstance(node, VNode):
        return _VNodePP(node, parent_edge=e, parent=p)
    else:
        return _QNodePP(node, parent_edge=e, parent=p)

class _NodePP:

    def __init__(self, node, parent_edge=None, parent=None):
        """node: either VNode or QNode (the actual node on the tree) """
        self.parent_edge = parent_edge
        self.parent = parent
        self.children = node.children
        self.print_children = True
        self.original = node

    @property
    def marked(self):
        return id(self.original) in MARKED

    def to_edge(self, key):
        if key in self.children:
            return key
        elif type(key) == int:
            edges = list(sorted_by_str(self.children.keys()))
            return edges[key]
        elif type(key) == str:
            chosen = max(self.children.keys(),
                         key=lambda edge: similar(str(edge), key))
            if similar(str(chosen), key) >= SIMILAR_THRESH:
                return chosen
        raise ValueError("Cannot access children with key {}".format(key))


    def __getitem__(self, key):
        """
        When debugging, you can access the child of a node by the key
        of the following types:
        - the key is an action or observation object that points to a child;
          that is, key in self.children is True.
        - the key is an integer corresponding to the list of children shown
          when printing the node in the debugger
        - the key is a string that is similar to the string
          version of any of the action or observation edges;
          the most similar one will be chosen; The threshold
          of similarity is SIMILAR_THRESH
        """
        edge = self.to_edge(key)
        return _node_pp(self.children[edge], e=edge, p=self)

    def p(self, max_depth=None, print_type="summary"):
        self.print_tree(max_depth=max_depth,
                        print_type=print_type)

    @property
    def pp(self):
        self.print_tree(max_depth=None)

    def print_tree(self, **options):
        """Prints the tree, rooted at self"""
        _NodePP._print_tree_helper(self, "", [None], 0, **options)

    @staticmethod
    def _print_tree_helper(root,
                           parent_edge,
                           branch_positions,  # list of 'first', 'middle', 'last' for each level prior to root
                           depth,   # depth of root
                           max_depth=None,
                           print_type="summary"):
        """
        pos_among_children is either 'first', 'middle', or 'last'
        """
        if max_depth is not None and depth > max_depth:
            return
        if root is None:
            return

        # Print the tree branches for all levels up to current root
        branches = ""
        preceding_positions = branch_positions[:-1]  # all positions except for current root
        for pos in preceding_positions:
            if pos is None:
                continue
            elif pos == "first" or pos == "middle":
                branches += "│    "
            else:  # "last"
                branches += "     "

        last_position = branch_positions[-1]
        if last_position is None:
            pass
        elif last_position == "first" or last_position == "middle":
            branches += "├─── "
        else:  # last
            branches += "└─── "

        root.print_children = False
        line = branches + str(root)
        if isinstance(root, VNode):
            line += typ.cyan("(depth="+str(depth)+")")

        print(line)

        for i, c in enumerate(sorted_by_str(root.children)):

            skip = True
            if root[c].marked:
                skip = False
            elif print_type == "complete":
                skip = False
            elif (root[c].num_visits > 1):
                skip = False
            if print_type == "bold-only" and not root[c].marked:
                skip = True

            if not skip:
                if isinstance(root[c], QNode):
                    next_depth = depth
                else:
                    next_depth = depth + 1

                if i == len(root.children) - 1:
                    next_pos = "last"
                elif i == 0:
                    next_pos = "first"
                else:
                    next_pos = "middle"

                _NodePP._print_tree_helper(root[c],
                                           c,
                                           branch_positions + [next_pos],
                                           next_depth,
                                           max_depth=max_depth,
                                           print_type=print_type)


class _QNodePP(_NodePP, QNode):
    """QNode for better printing"""
    def __init__(self, qnode, **kwargs):
        QNode.__init__(self, qnode.num_visits, qnode.value)
        _NodePP.__init__(self, qnode, **kwargs)

    def __str__(self):
        return TreeDebugger.single_node_str(self,
                                            parent_edge=self.parent_edge,
                                            include_children=self.print_children)

class _VNodePP(_NodePP, VNode):
    """VNode for better printing"""
    def __init__(self, vnode, **kwargs):
        VNode.__init__(self, vnode.num_visits)
        _NodePP.__init__(self, vnode, **kwargs)

    def __str__(self):
        return TreeDebugger.single_node_str(self,
                                            parent_edge=self.parent_edge,
                                            include_children=self.print_children)


class TreeDebugger:
    """
    Helps you debug the search tree; A search tree is a tree
    that contains a subset of future histories, organized into
    QNodes (value represents Q(b,a); children are observations) and
    VNodes (value represents V(b); children are actions).
    """
    def __init__(self, tree):
        """
        Args:
            tree (VNode): the root node of a search tree. For example,
                the tree built by POUCT after planning an action,
                which can be accessed by agent.tree.
        """
        if not isinstance(tree, TreeNode):
            raise ValueError("Expecting tree to be a TreeNode, but got {}".format(type(tree)))

        self.tree = _node_pp(tree)
        self.current = self.tree   # points to the node the user is interacting with
        self._stats_cache = {}

    def __str__(self):
        return str(self.current)

    def __repr__(self):
        nodestr = TreeDebugger.single_node_str(self.current,
                                               parent_edge=self.current.parent_edge)
        return "TreeDebugger@\n{}".format(nodestr)

    def __getitem__(self, key):
        return self.current[key]

    def _get_stats(self):
        if id(self.current) in self._stats_cache:
            stats = self._stats_cache[id(self.current)]
        else:
            stats = TreeDebugger.tree_stats(self.current)
            self._stats_cache[id(self.current)] = stats
        return stats

    def num_nodes(self, kind='all'):
        """
        Returns the total number of nodes in the tree rooted at "current"
        """
        stats = self._get_stats()
        res = {
            'all': stats['total_vnodes'] + stats['total_qnodes'],
            'q': stats['total_qnodes'],
            'v': stats['total_vnodes']
        }
        if kind in res:
            return res[kind]
        else:
            raise ValueError("Invalid value for kind={}; Valid values are {}"\
                             .format(kind, list(res.keys())))


    @property
    def depth(self):
        """Tree depth starts from 0 (root node only).
        It is the largest number of edges on a path from root to leaf."""
        stats = self._get_stats()
        return stats['max_depth']

    @property
    def d(self):
        """alias for depth"""
        return self.depth

    @property
    def num_layers(self):
        """Returns the number of layers;
        It is the number of layers of nodes, which equals to depth + 1"""
        return self.depth + 1

    @property
    def nl(self):
        """alias for num_layers"""
        return self.num_layers

    @property
    def nn(self):
        """Returns the total number of nodes in the tree"""
        return self.num_nodes(kind='all')

    @property
    def nq(self):
        """Returns the total number of QNodes in the tree"""
        return self.num_nodes(kind='q')

    @property
    def nv(self):
        """Returns the total number of VNodes in the tree"""
        return self.num_nodes(kind='v')

    def l(self, depth, as_debuggers=True):
        """alias for layer"""
        return self.layer(depth, as_debuggers=as_debuggers)

    def layer(self, depth, as_debuggers=True):
        """
        Returns a list of nodes at the given depth. Will only return VNodes.
        Warning: If depth is high, there will likely be a huge number of nodes.

        Args:
            depth (int): Depth of the tree
            as_debuggers (bool): True if return a list of TreeDebugger objects,
                one for each tree on the layer.
        """
        if depth < 0 or depth > self.depth:
            raise ValueError("Depth {} is out of range (0-{})".format(depth, self.depth))
        nodes = []
        self._layer_helper(self.current, 0, depth, nodes)
        return nodes

    def _layer_helper(self, root, current_depth, target_depth, nodes, as_debuggers=True):
        if current_depth == target_depth:
            if isinstance(root, VNode):
                if as_debuggers:
                    nodes.append(TreeDebugger(root))
                else:
                    nodes.append(root)
        else:
            for c in sorted_by_str(root.children):
                if isinstance(root[c], QNode):
                    next_depth = current_depth
                else:
                    next_depth = current_depth + 1
                self._layer_helper(root[c],
                                   next_depth,
                                   target_depth,
                                   nodes)

    def step(self, key):
        """Updates current interaction node to follow the
        edge along key"""
        edge = self.current.to_edge(key)
        self.current = self[edge]
        print("step: " + str(edge))


    def s(self, key):
        """alias for step"""
        return self.step(key)

    def back(self):
        """move current node of interaction back to parent"""
        self.current = self.current.parent

    @property
    def b(self):
        """alias for back"""
        self.back()

    @property
    def root(self):
        """The root node when first creating this TreeDebugger"""
        return self.tree

    @property
    def r(self):
        """alias for root"""
        return self.root

    @property
    def c(self):
        """Current node of interaction"""
        return self.current

    def p(self, *args, **kwargs):
        """print tree"""
        return self.current.p(*args, **kwargs)

    @property
    def pp(self):
        """print tree, with preset options"""
        return self.current.pp

    def mark_sequence(self, seq):
        """
        Given a list of keys (understandable by __getitem__ in _NodePP),
        mark nodes (both QNode and VNode) along the path in the tree.
        Note this sequence starts from self.current; So self.current will
        also be marked.
        """
        node = self.current
        MARKED.add(id(node.original))
        for key in seq:
            MARKED.add(id(node[key].original))
            node = node[key]

    def mark(self, seq):
        """alias for mark_sequence"""
        return self.mark_sequence(seq)

    @property
    def bestseq(self):
        """Returns a list of actions, observation sequence
        that have the highest value for each step. Such
        a sequence is "preferred".

        Also, prints out the list of preferred actions for each step
        into the future"""
        return self.preferred_actions(self.current, max_depth=None)

    def bestseqd(self, max_depth):
        """
        alias for bestseq except with
        """
        return self.preferred_actions(self.current, max_depth=max_depth)

    @staticmethod
    def single_node_str(node, parent_edge=None, indent=1, include_children=True):
        """
        Returns a string for printing given a single vnode.
        """
        if hasattr(node, "marked") and node.marked:
            opposite_color = color = lambda s: typ.bold(typ.yellow(s))
        elif isinstance(node, VNode):
            color = typ.green
            opposite_color = typ.red
        else:
            assert isinstance(node, QNode)
            color = typ.red
            opposite_color = typ.green

        output = ""
        if parent_edge is not None:
            output += opposite_color(str(parent_edge)) + "⟶"

        output += color(str(node.__class__.__name__))\
            + "(n={}, v={:.3f})".format(node.num_visits,
                                    node.value)
        if include_children:
            output += "\n"
            for i, action in enumerate(sorted_by_str(node.children)):
                child = node.children[action]
                child_info = TreeDebugger.single_node_str(child, include_children=False)

                spaces = "    " * indent
                output += "{}- [{}] {}: {}".format(spaces, i,
                                                   typ.white(str(action)),
                                                   child_info)
                if i < len(node.children) - 1:
                    output += "\n"
            output += "\n"
        return output

    @staticmethod
    def preferred_actions(root, max_depth=None):
        """
        Print out the currently preferred actions up to given `max_depth`
        """
        seq = []
        TreeDebugger._preferred_actions_helper(root, 0, seq, max_depth=max_depth)
        return seq

    @staticmethod
    def _preferred_actions_helper(root, depth, seq, max_depth=None):
        # don't care about last layer action because it's outside of planning
        # horizon and only has initial value.
        if max_depth is not None and depth > max_depth:
            return
        best_child = None
        best_value = float('-inf')
        if root is None or len(root.children) == 0:
            return
        for c in root.children:
            if root[c].value > best_value:
                best_child = c
                best_value = root[c].value
        seq.append(best_child)
        equally_good = []
        if isinstance(root, VNode):
            for c in root.children:
                if not(c == best_child) and root[c].value == best_value:
                    equally_good.append(c)

        if best_child is not None and root[best_child] is not None:
            if isinstance(root[best_child], QNode):
                print("  %s  %s" % (typ.yellow(str(best_child)), str(equally_good)))
                next_depth = depth
            else:
                next_depth = depth + 1

            TreeDebugger._preferred_actions_helper(root[best_child], next_depth, seq,
                                                   max_depth=max_depth)

    @staticmethod
    def tree_stats(root, max_depth=None):
        """Gether statistics about the tree"""
        stats = {
            'total_vnodes': 0,
            'total_qnodes': 0,
            'total_vnodes_children': 0,
            'total_qnodes_children': 0,
            'max_vnodes_children': 0,
            'max_qnodes_children': 0,
            'max_depth': 0
        }
        TreeDebugger._tree_stats_helper(root, 0, stats, max_depth=max_depth)
        stats['num_visits'] = root.num_visits
        stats['value'] = root.value
        return stats

    @staticmethod
    def _tree_stats_helper(root, depth, stats, max_depth=None):
        if max_depth is not None and depth > max_depth:
            return
        else:
            if isinstance(root, VNode):
                stats['total_vnodes'] += 1
                stats['total_vnodes_children'] += len(root.children)
                stats['max_vnodes_children'] = max(stats['max_vnodes_children'], len(root.children))
                stats['max_depth'] = max(stats['max_depth'], depth)
            else:
                stats['total_qnodes'] += 1
                stats['total_qnodes_children'] += len(root.children)
                stats['max_qnodes_children'] = max(stats['max_qnodes_children'], len(root.children))

            for c in root.children:
                if isinstance(root[c], QNode):
                    next_depth = depth
                else:
                    next_depth = depth + 1
                TreeDebugger._tree_stats_helper(root[c], next_depth, stats, max_depth=max_depth)