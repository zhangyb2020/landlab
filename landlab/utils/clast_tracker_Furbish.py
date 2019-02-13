#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
Created in Oct 12 2017

@author: margauxmouchene
"""
# Must be used with a component that explicitly calculates erosion, deposition,
# sediment influx on each node.
# Must be run after each time step where the above component is used
# (AFTER topography is updated)
# before uplift is applied ?
# uplift must be a field defined at nodes [L/T]

import numpy as np
import gc


class ClastSet(object):

    def __init__(self,
                 grid,
                 clast__node,
                 clast__elev,
                 clast__radius,
                 erosion_method='TLDiff'):
#        space_name='space'

        # Store grid, elevation field and time step
        self._grid = grid
        self._elev = grid.at_node['topographic__elevation']
        self._distances = self._grid.all_node_distances_map

        # Clast position arrays:
        self._clast__node = clast__node
        self._clast__elev = clast__elev   # !!!ELEV OF CLAST BASE!!!

        # Clast size (radius):
        self._clast__radius = clast__radius  # in meters

        # Clast set size:
        self._set__size = len(self._clast__node)

        # Receiver nodes (from flow router/director method)
        self._receiver = self._grid.at_node['flow__receiver_node']

        # Method loop: Depending on the method used to evolve the landscape,
        # get sediment influx, erosion and deposition
        self.erosion_method = erosion_method
        if self.erosion_method == 'TLDiff':
            self._erosion_rate = self._grid.at_node['sediment__erosion_rate']
            self._deposition_rate = self._grid.at_node['sediment__deposition_rate']
            self._sediment__flux_in = self._grid.at_node['sediment__flux_in']
        elif self.erosion_method == 'Space':
            from landlab.components import Space
            for obj in gc.get_objects():
                if isinstance(obj, Space):    # look for instance of Space
                    self._erosion_rate = obj.Es + obj.Er   # Works if only one instance of Space was made
                    self._deposition_rate = obj.depo_rate
                    self._sediment__flux_in = obj.qs_in
            # self.space = space_name CAN'T CALL INSTANCE FROM INPUT STRING NAME

        # Future version: multiple compo -> add fluxes?

        # Create array recording travelled distance for each clast
        if hasattr(self, '_clast__distance'):
            pass
        else:
            self._clast__distance = np.zeros(self._set__size)

        for i in range(self._set__size):
            # If initial clast elevation is above topographic elev, 
            # set clast elev to topo elev:
            if self._clast__elev[i] > self._elev[self._clast__node[i]]:
                self._clast__elev[i] = self._elev[self._clast__node[i]]

        self._position = np.array((self._clast__node, self._clast__elev))
        self._clast__x = np.array((self._grid.node_x[self._clast__node]))
        self._clast__y = np.array((self._grid.node_y[self._clast__node]))

        self._dt = np.zeros(1)
        self._erosion__depth = np.zeros(grid.number_of_nodes)
        self._deposition__thickness = np.zeros(grid.number_of_nodes)
        self._deposition__flux = np.zeros(grid.number_of_nodes)

    def clast_solver_furbish(self, dt=1., critical_slope=1.2, uplift=None):

# Repeated from above??
        if self.erosion_method == 'TLDiff':
            self._erosion_rate = self._grid.at_node['sediment__erosion_rate']
            self._deposition_rate = self._grid.at_node['sediment__deposition_rate']
            self._sediment__flux_in = self._grid.at_node['sediment__flux_in']
        elif self.erosion_method == 'Space':
            from landlab.components import Space
            for obj in gc.get_objects():
                if isinstance(obj, Space):    # look for instance of Space
                    self._erosion_rate = obj.Es + obj.Er   # Works if only one instance of Space was made
                    self._deposition_rate = obj.depo_rate
                    self._sediment__flux_in = obj.qs_in

        # Store various values that will be used
        self._Sc = critical_slope
        self._dt = dt
        self._erosion__depth = self._erosion_rate * self._dt
        self._deposition__thickness = self._deposition_rate * self._dt
# TO DELETE???        self._deposition__flux = self._deposition_rate # * self._grid.dx


        if uplift is not None:
            if type(uplift) is str:
                self._uplift = self._grid.at_node[uplift]
            elif type(uplift) in (float, int):
                self._uplift = np.ones(self._grid.number_of_nodes) * (
                        float(uplift))
            elif len(uplift) == self._grid.number_of_nodes:
                self._uplift = np.array(uplift)
            else:
                raise TypeError('Supplied type of uplift is not recognized')


        for i in range(self._set__size):   # Treat clasts one after the other
            # Test if clast in grid core (=not phantom)
            if ClastSet.phantom(self, i) == False:
                #print('not phantom')
                # Clast is in grid core
                # Test if clast is detached:
                if ClastSet.clast_detach_proba(self, i) == True:
                    #print('detached')
                    # Clast is detached -> Test if moves (leaves node):
                    if ClastSet.clast_move_proba(self, i) == True:
                        # print('move')
                        # Clast leaves node:
                        # Clast is moved to next node downstream:
                        node_i = self._clast__node[i]
                        receiver_i = self._grid.at_node['flow__receiver_node'][self._clast__node[i]]
                        
                        # Update travelled distance:
                        self._clast__distance[i] += np.sqrt(np.power(
                                self._distances[node_i, receiver_i],2)+(np.power(
                                        self._grid.at_node['topographic__elevation'][node_i]-self._grid.at_node['topographic__elevation'][receiver_i],2)))
                        # Move clast to next downstream:
                        self._clast__node[i] = (
                                self._receiver[self._clast__node[i]])
                        # if multiple flow:
                        # random nb against Si/sum(Si)

                        # Clast has been moved to new node -> Test if
                        # deposited:
                        # While clast is not deposited, keeps changing node:
                        while ClastSet.clast_depo_proba(self, i) == False:
                            if ClastSet.phantom(self, i) == False:
                                #print(i)
                                #print('not depositing')
                                # Update travelled distance:
                                self._clast__distance[i] += np.sqrt(np.power(
                                        self._distances[node_i, receiver_i],2)+(np.power(
                                                self._grid.at_node['topographic__elevation'][node_i]-self._grid.at_node['topographic__elevation'][receiver_i],2)))
                                # Clast is moved to next node downstream
                                self._clast__node[i] = (
                                        self._receiver[self._clast__node[i]])
                            else:
                                break
                    
                    # next section instead of following 2 parag, to update clast elev at the end of this timestep as somewhere in the deposited layer?
                    else:
                        pass

                    # Update clast elevation: clast is reworked in the 
                    # newly deposited layer
                    self._clast__elev[i] = self._elev[self._clast__node[i]] - (
                            self._deposition__thickness[self._clast__node[i]] * (np.random.rand(1)))

#TO DELETE#######################################################################
#                        # Finally, clast  is deposited:
#                        # Update clast elevation:
#                        self._clast__elev[i] = self._elev[
#                                self._clast__node[i]] - (
#                                self._deposition__thickness[
#                                        self._clast__node[i]] * (
#                                        np.random.rand(1)))
#
#                    else:
#                        # Clast does not leave node -> update elevation
#                        self._clast__elev[i] = self._elev[self._clast__node[i]]
#                        pass
################################################################################

                else:
                    # Clast is not detached -> go to next clast
                    pass

            if hasattr(self, '_uplift') is True:
                self._clast__elev[i] += self._uplift[self._clast__node[i]] * self._dt

            else:
                # Clast is phantom -> go to next clast
                # for display purpose: phantom clast has a radius of 0
                # self._clast__radius(i) = 0.
                pass
#
#        for i in range(self._set__size):
#            if hasattr(ClastSet, '_uplift') is True:
#                self._clast__elev[i] += 0   # self._uplift[self._clast__node[i]] * (np.ones(self._set__size) * self._dt)

#        for i in range(self._set__size):
#                # Test if clast has now exited core nodes (is phantom):
#                # If not, add uplift to elev clast:
#            if ClastSet.phantom(self, i) is True:
#                self._clast__elev[i] = self._elev[self._clast__node[i]]
#                # self._clast__radius[i] = 0
#            else:
#                if hasattr(ClastSet, '_uplift') is True:
#                    # if clast not phantom & uplift not none,
#                    # clast if uplifted
#                    self._clast__elev[i] += self._uplift[
#                            self._clast__node[i]] * self._dt

        self._clast__x = np.array((self._grid.node_x[self._clast__node]))
        self._clast__y = np.array((self._grid.node_y[self._clast__node]))
        self._position = np.array((self._clast__node, self._clast__elev))
        # array ([node_IDs], [elev])



    # @classmethod   # ? or @staticmethod?
    def clast_detach_proba(self, i):
        # Test if clast is detached:
        # clast is detached if erosion is sufficient to expose its base
        clast__elev = self._clast__elev[i]
        topo__elev = self._elev[self._clast__node[i]]
        erosion = self._erosion__depth[self._clast__node[i]]

        _det = np.zeros(1, dtype=bool)

        if erosion >= topo__elev - clast__elev:
        # Previously: 
        # if clast__elev >= topo__elev:
            _det = True

        return _det

    def clast_move_proba(self, i):
        # Clast moves if its probability to move is higher than
        # a random number
        erosion = self._erosion__depth[self._clast__node[i]]
        radius = self._clast__radius[i]
        clast__depth = self._elev[self._clast__node[i]] - self._clast__elev[i]
        potential_distance = self._distances[self._clast__node[i],self._grid.at_node['flow__receiver_node'][self._clast__node[i]]]

        R = np.random.rand(1)

        
        # Furbish & Roering 2013: Disentrainment rate = proba that a particle
        # will come to rest within [r, r+dr] given that it moved to a distance
        # at least as far as r, starting from x'
        
        lambda_0 = 1.
        Sc = self._Sc
        S = self._elev[self._clast__node[i]] - self._elev[self._grid.at_node['flow__receiver_node'][self._clast__node[i]]]
        
        proba_rest = (1 / lambda_0) * (((2 * Sc) / (Sc + S))-1)
        
        
        
        
        if erosion > 0:
            if potential_distance in (self._grid.dx, self._grid.dy):

                # if clast will potentially move in row or column
                proba_move = 1.9 * ((erosion) / (
                        2 * radius)) * (1-(clast__depth / erosion))
            else:   # clast will potentially move in diagonal
                proba_move = (1 / np.sqrt(2)) * 1.9 * ((erosion) / (
                        2 * radius)) * (1-(clast__depth / erosion))

#                # if clast will potentially move in row or column
#                proba_move = ((erosion) / (
#                        2 * radius)) * (1-(clast__depth / erosion))
#            else:   # clast will potentially move in diagonal
#                proba_move = (1 / np.sqrt(2)) * ((erosion) / (
#                        2 * radius)) * (1-(clast__depth / erosion))

            # proba_move can be >1 (if clast was at surface) -> set to 1 
            if proba_move > 1:
                proba_move = 1
        else:
            proba_move = 0

        _move = np.zeros(1, dtype=bool)

        if proba_move >= R:
            # Clast leaves node:
            _move = True
        else:
            _move = False

        return _move

    def clast_depo_proba(self, i):

        # Clast is deposited if its probability to be deposited is
        # higher than a random number.
        depo = self._deposition_rate[self._clast__node[i]]
        fluxin = self._sediment__flux_in[self._clast__node[i]]
        R = np.random.rand(1)

        # To avoid divide by 0 if no flux in, proba is set to 1
        if fluxin == 0.:
            proba_depo = 1.
        else:
            proba_depo = depo / fluxin
# TO ADD: deposition proba should be dependent on clast size!

        _depo = np.zeros(1, dtype=bool)

        if proba_depo < R:
            # Clast  is not deposited
            _depo = False
            #print(proba_depo)
        else:
            _depo = True

        return _depo

    def phantom(self, i):
        # When a clast reaches a boundary node, it exits the grid and is thus
        # flagged as phantom
        # To add: Also phantom when totally dissovled (radius = 0)
        clast_node = self._clast__node[i]
        boundary_nodes = self._grid.boundary_nodes
        _phantom = np.zeros(1, dtype=bool)

        if clast_node in boundary_nodes:
            _phantom = True

        return _phantom


    @property
    def position(self):
        return self._position

    @property
    def coordinate(self):
        return self._clast__coord

    @property
    def distance(self):
        return self._clast__distance

    @property
    def size(self):
        return self._clast__radius
