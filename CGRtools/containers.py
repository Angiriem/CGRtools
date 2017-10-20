# -*- coding: utf-8 -*-
#
#  Copyright 2017 Ramil Nugmanov <stsouko@live.ru>
#  This file is part of CGRtools.
#
#  CGRtools is free software; you can redistribute it and/or modify
#  it under the terms of the GNU Affero General Public License as published by
#  the Free Software Foundation; either version 3 of the License, or
#  (at your option) any later version.
#
#  This program is distributed in the hope that it will be useful,
#  but WITHOUT ANY WARRANTY; without even the implied warranty of
#  MERCHANTABILITY or FITNESS FOR A PARTICULAR PURPOSE.  See the
#  GNU Affero General Public License for more details.
#
#  You should have received a copy of the GNU Affero General Public License
#  along with this program; if not, write to the Free Software
#  Foundation, Inc., 51 Franklin Street, Fifth Floor, Boston,
#  MA 02110-1301, USA.
#
from collections import namedtuple
from itertools import chain
from networkx import Graph, relabel_nodes
from networkx.readwrite.json_graph import node_link_graph, node_link_data
from warnings import warn
from .algorithms import get_morgan, get_cgr_string, hash_cgr_string

CGRTemplate = namedtuple('CGRTemplate', ['reagents', 'products', 'meta'])
MatchContainer = namedtuple('MatchContainer', ['mapping', 'meta', 'patch'])


class MergedReaction(namedtuple('MergedReaction', ['reagents', 'products'])):
    def copy(self):
        return MergedReaction(self.reagents.copy(), self.products.copy())


class MoleculeContainer(Graph):
    def __init__(self, meta=None):
        super().__init__()
        if isinstance(meta, dict):
            self.__meta = meta

    def __dir__(self):
        if self.__visible is None:
            self.__visible = [self.pickle.__name__, self.unpickle.__name__, self.copy.__name__, self.subgraph.__name__,
                              self.remap.__name__, self.add_stereo.__name__, self.get_morgan.__name__,
                              self.get_fear.__name__, self.get_fear_hash.__name__,
                              self.get_environment.__name__, self.fix_data.__name__, self.reset_query_marks.__name__,
                              self.atom.__name__, self.bond.__name__, self.add_atom.__name__, self.add_bond.__name__,
                              'meta', 'bonds_count', 'atoms_count']  # properties names inaccessible
        return self.__visible

    def pickle(self):
        """ return json serializable CGR or Molecule
        """
        if isinstance(self, CGRContainer):
            s_only = False
            node_marks = self._node_sp
            edge_marks = self._edge_sp
        else:
            s_only = True
            node_marks = self._node_s
            edge_marks = self._edge_s

        g = Graph()
        g.add_nodes_from((n, {k: v for k, v in a.items() if k in node_marks}) for n, a in self.nodes(data=True))
        g.add_edges_from((n, m, {k: v for k, v in a.items() if k in edge_marks}) for n, m, a in self.edges(data=True))

        data = node_link_data(g, attrs=self.__attrs)
        data.update(meta=self.meta, s_only=s_only)
        return data

    @classmethod
    def unpickle(cls, data):
        """ convert json serializable CGR into MoleculeContainer or CGRcontainer object instance
        """
        g = node_link_graph(data, attrs=cls.__attrs)
        g.__class__ = MoleculeContainer if data['s_only'] else CGRContainer
        g.fix_data()
        g.meta.update(data['meta'])
        return g

    def copy(self):
        copy = super().copy()
        copy.__class__ = self.__class__
        copy.meta.update(self.meta)
        return copy

    def subgraph(self, nbunch, meta=False):
        sub = super().subgraph(nbunch).copy()
        sub.__class__ = self.__class__
        if meta:
            sub.meta.update(self.meta)
        sub._fix_stereo()
        return sub

    def remap(self, mapping, copy=False):
        g = relabel_nodes(self, mapping, copy=copy)
        if copy:
            g.__class__ = self.__class__
        return g

    @property
    def meta(self):
        if self.__meta is None:
            self.__meta = {}
        return self.__meta

    def add_stereo(self, atom1, atom2, mark):
        if self.has_edge(atom1, atom2):
            # todo: stereo calc
            pass

    def get_stereo(self, atom1, atom2):
        # todo: implement stereo to bond projection
        return None, None

    def get_fear_hash(self, weights=None, isotope=False, stereo=False, hyb=False, element=True):
        return hash_cgr_string(self.get_fear(weights=weights, isotope=isotope, stereo=stereo, hyb=hyb, element=element))

    def get_fear(self, weights=None, isotope=False, stereo=False, hyb=False, element=True):
        """
        :param weights: dict of atoms in keys and orders in values 
        :param isotope: set isotope marks
        :param stereo: set stereo marks
        :param hyb: set hybridization mark of atom
        :param element: set elements marks
        :return: string representation of CGR
        """
        return get_cgr_string(self, weights or get_morgan(self, isotope=isotope, element=element),
                              isotope=isotope, stereo=stereo, hyb=hyb, element=element)

    def add_atom(self, element, s_charge, _map=None, mark='0', x=0, y=0, z=0):
        if _map is None:
            _map = max(self, default=0) + 1
        elif _map in self:
            raise Exception('mapping exists')

        # todo: charges and elements checks.

        self.add_node(_map, element=element, s_charge=s_charge, mark=mark, s_x=x, s_y=y, s_z=z, map=_map)

    def add_bond(self, atom1, atom2, mark):
        if atom1 not in self or atom2 not in self:
            raise Exception('atoms not found')
        if not mark:
            raise Exception('no bond data')

        self.add_edge(atom1, atom2, s_bond=mark)

    def bond(self, atom1, atom2):
        return self[atom1][atom2]

    def atom(self, n):
        return self.nodes[n]

    @property
    def bonds_count(self):
        return self.size()

    @property
    def atoms_count(self):
        return self.order()

    def get_environment(self, atoms, dante=False, deep=0):
        """ get subgraph with atoms and their neighbors
        :param atoms: list of core atoms in graph
        :param dante: if True return list of graphs containing atoms, atoms + first circle, atoms + 1st + 2nd, 
        etc up to deep or while new nodes available.
        :param deep: number of bonds between atoms and neighbors. 
        """
        nodes = [set(atoms)]
        for i in range(deep):
            n = set(chain.from_iterable(self.edges(nodes[i])))
            if not n or n in nodes:
                break
            nodes.append(n)

        if dante:
            centers = [self.subgraph(a) for a in nodes]
        else:
            centers = self.subgraph(nodes[-1])

        return centers

    def get_morgan(self, isotope=False, element=True, stereo=False):
        return get_morgan(self, isotope=isotope, element=element, stereo=stereo)

    def fix_data(self, copy=False, nodes_bunch=None, edges_bunch=None):
        g = self.copy() if copy else self
        for a in ((a for _, a in g.nodes(data=True)) if nodes_bunch is None else
                  (g.nodes[x] for x in g.nbunch_iter(nodes_bunch))):
            new = self._attr_renew(a, self._node_marks)
            a.clear()
            a.update(new)

        for *_, a in g.edges(nbunch=edges_bunch, data=True):
            new = self._attr_renew(a, self._edge_marks)
            a.clear()
            a.update(new)
        return g if copy else None

    def reset_query_marks(self, copy=False):
        """
        set or reset hyb and neighbors marks to atoms. 
        :param copy: if True return copy of graph and keep existing as is
        :return: graph if copy True else None
        """
        g = self.copy() if copy else self
        b, h, n = 's_bond', 's_hyb', 's_neighbors'
        for i in g:
            label = dict(s_hyb=1, p_hyb=1, s_neighbors=0, p_neighbors=0)
            #  hyb 1- sp3; 2- sp2; 3- sp1; 4- aromatic
            for node, bond in g[i].items():
                b_type = bond.get(b)
                if b_type and g.nodes[node]['element'] != 'H':
                    label[n] += 1
                if b_type in (1, None) or label[h] in (3, 4):
                    continue
                elif b_type == 4:
                    label[h] = 4
                elif b_type == 3 or (b_type == 2 and label[h] == 2):  # Если есть 3-я или две 2-х связи, то sp1
                    label[h] = 3
                elif b_type == 2 and label[h] != 3:
                    # Если есть 2-я связь, но до этого не было найдено другой 2-й, 3-й, или аром.
                    label[h] = 2

            g.nodes[i].update(label)
        return g if copy else None

    @staticmethod
    def _attr_renew(attr, marks):
        new_attr = {}
        for s in marks:
            ls = attr.get(s)
            if ls is not None:
                new_attr[s] = ls
        return new_attr

    def _fix_stereo(self):
        pass

    __attrs = dict(source='atom1', target='atom2', name='atom', link='bonds')
    __node_base = ('element', 'isotope', 'mark', 's_x', 's_y', 's_z')
    _node_marks = ('s_neighbors', 's_hyb', 's_charge', 's_stereo')
    _node_s = _node_marks + __node_base
    _edge_s = _edge_marks = ('s_bond', 's_stereo')
    __meta = __visible = None


class CGRContainer(MoleculeContainer):
    def __dir__(self):
        if self.__visible is None:
            self.__visible = tmp = super().__dir__()
            tmp.append(self.get_center_atoms.__name__)
        return self.__visible

    def get_center_atoms(self, stereo=False):
        """ get atoms of reaction center (dynamic bonds, stereo or charges).
        """
        # todo: stereo
        nodes = set()
        for n, node_attr in self.nodes(data=True):
            if node_attr.get('s_charge') != node_attr.get('p_charge'):
                nodes.add(n)

        for *n, node_attr in self.edges(data=True):
            if node_attr.get('s_bond') != node_attr.get('p_bond'):
                nodes.update(n)

        return list(nodes)

    def add_atom(self, element, s_charge, p_charge=None, _map=None, mark='0',
                 s_x=0, s_y=0, s_z=0, p_x=None, p_y=None, p_z=None):
        if _map is None:
            _map = max(self, default=0) + 1
        elif _map in self:
            raise Exception('mapping exists')

        # todo: charges and elements checks.

        if p_charge is None:
            p_charge = s_charge
        if p_x is None:
            p_x = s_x
        if p_y is None:
            p_y = s_y
        if p_z is None:
            p_z = s_z

        self.add_node(_map, element=element, s_charge=s_charge, p_charge=p_charge, mark=mark,
                      s_x=s_x, s_y=s_y, s_z=s_z, p_x=p_x, p_y=p_y, p_z=p_z, map=_map)

    def add_bond(self, atom1, atom2, s_mark, p_mark):
        if atom1 not in self or atom2 not in self:
            raise Exception('atoms not found')
        attr = {}
        if s_mark:
            attr['s_bond'] = s_mark
        if p_mark:
            attr['p_bond'] = p_mark
        if not attr:
            raise Exception('no bonds data')
        self.add_edge(atom1, atom2, **attr)

    def add_stereo(self, atom1, atom2, s_mark, p_mark):
        if self.has_edge(atom1, atom2):
            # todo: stereo calc
            pass

    def reset_query_marks(self, copy=False):
        """
        set or reset hyb and neighbors marks to atoms.
        :param copy: if True return copy of graph and keep existing as is
        :return: graph if copy True else None
        """
        g = self.copy() if copy else self
        for i in g:
            label = dict(s_hyb=1, p_hyb=1, sp_hyb=1, s_neighbors=0, p_neighbors=0, sp_neighbors=0)
            #  hyb 1- sp3; 2- sp2; 3- sp1; 4- aromatic
            for b, h, n in (('s_bond', 's_hyb', 's_neighbors'), ('p_bond', 'p_hyb', 'p_neighbors')):
                for node, bond in g[i].items():
                    b_type = bond.get(b)
                    if b_type and g.nodes[node]['element'] != 'H':
                        label[n] += 1
                    if b_type in (1, None) or label[h] in (3, 4):
                        continue
                    elif b_type == 4:
                        label[h] = 4
                    elif b_type == 3 or (b_type == 2 and label[h] == 2):  # Если есть 3-я или две 2-х связи, то sp1
                        label[h] = 3
                    elif b_type == 2 and label[h] != 3:
                        # Если есть 2-я связь, но до этого не было найдено другой 2-й, 3-й, или аром.
                        label[h] = 2

            for n, m, h in (('s_hyb', 'p_hyb', 'sp_hyb'), ('s_neighbors', 'p_neighbors', 'sp_neighbors')):
                label[h] = (label[n], label[m]) if label[n] != label[m] else label[n]

            g.nodes[i].update(label)
        return g if copy else None

    def _fix_stereo(self):
        pass

    @staticmethod
    def _attr_renew(attr, marks):
        new_attr = {}
        for s, p, sp in marks:
            ls = attr.get(s)
            lp = attr.get(p)

            if isinstance(ls, list):
                if isinstance(lp, list):
                    if ls == lp:
                        new_attr[sp] = new_attr[s] = new_attr[p] = list(set(ls))
                        continue
                    new_attr[sp] = list(set((x, y) for x, y in zip(ls, lp) if x != y))
                else:
                    new_attr[sp] = list(set((x, lp) for x in ls if x != lp))

                new_attr[s] = [x for x, _ in new_attr[sp]]
                new_attr[p] = [x for _, x in new_attr[sp]]
            elif isinstance(lp, list):
                new_attr[sp] = list(set((ls, x) for x in lp if x != ls))
                new_attr[s] = [x for x, _ in new_attr[sp]]
                new_attr[p] = [x for _, x in new_attr[sp]]
            elif ls != lp:
                new_attr[sp] = (ls, lp)
            elif ls is not None:
                new_attr[sp] = ls
        return new_attr

    __node_base = ('element', 'isotope', 'mark', 's_x', 's_y', 's_z')
    _node_marks = tuple(('s_%s' % mark, 'p_%s' % mark, 'sp_%s' % mark)
                        for mark in ('neighbors', 'hyb', 'charge', 'stereo'))
    _edge_marks = tuple(('s_%s' % mark, 'p_%s' % mark, 'sp_%s' % mark) for mark in ('bond', 'stereo'))
    _node_sp = tuple(chain((y for x in _node_marks for y in x[:2]), __node_base, ('p_x', 'p_y', 'p_z')))
    _edge_sp = ('s_bond', 'p_bond', 's_stereo', 'p_stereo')
    __visible = None


class ReactionContainer(object):
    __slots__ = ('__reagents', '__products', '__reactants', '__meta')

    def __init__(self, substrats=None, products=None, reactants=None, meta=None, reagents=None):
        if substrats:
            warn('deprecated key. use reagents instead', DeprecationWarning)

        self.__reagents = substrats or reagents or []
        self.__products = products or []
        self.__reactants = reactants or []
        self.__meta = meta or {}

    def __getitem__(self, item):
        if item == 'substrats':
            warn('deprecated key. use reagents instead', DeprecationWarning)
            return self.__reagents
        elif item == 'reagents':
            return self.__reagents
        elif item == 'products':
            return self.__products
        elif item == 'reactants':
            return self.__reactants
        elif item == 'meta':
            return self.__meta
        else:
            raise Exception('Invalid key')

    def pickle(self):
        """ return json serializable reaction
        """
        return dict(reagents=[x.pickle() for x in self.__reagents], meta=self.meta,
                    products=[x.pickle() for x in self.__products], reactants=[x.pickle() for x in self.__reactants])

    @staticmethod
    def unpickle(data):
        """ convert json serializable reaction into ReactionContainer object instance 
        """
        return ReactionContainer(reagents=[MoleculeContainer.unpickle(x) for x in
                                           (data['reagents'] if 'reagents' in data else data['substrats'])],
                                 products=[MoleculeContainer.unpickle(x) for x in data['products']], meta=data['meta'],
                                 reactants=[MoleculeContainer.unpickle(x) for x in data.get('reactants', [])])

    @property
    def substrats(self):  # reverse compatibility
        warn('deprecated key. use reagents instead', DeprecationWarning)
        return self.__reagents

    @property
    def reagents(self):
        return self.__reagents

    @property
    def products(self):
        return self.__products

    @property
    def reactants(self):
        return self.__reactants

    @property
    def meta(self):
        return self.__meta

    def copy(self):
        return ReactionContainer(reagents=[x.copy() for x in self.__reagents], meta=self.__meta.copy(),
                                 products=[x.copy() for x in self.__products],
                                 reactants=[x.copy() for x in self.__reactants])