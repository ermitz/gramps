#
# Gramps - a GTK+/GNOME based genealogy program
#
# Copyright (C) 2017-2018 Nick Hall
#
# This program is free software; you can redistribute it and/or modify
# it under the terms of the GNU General Public License as published by
# the Free Software Foundation; either version 2 of the License, or
# (at your option) any later version.
#
# This program is distributed in the hope that it will be useful,
# but WITHOUT ANY WARRANTY; without even the implied warranty of
# MERCHANTABILITY or FITNESS FOR A PARTICULAR PURPOSE.  See the
# GNU General Public License for more details.
#
# You should have received a copy of the GNU General Public License
# along with this program; if not, write to the Free Software
# Foundation, Inc., 51 Franklin Street, Fifth Floor, Boston, MA 02110-1301 USA.
#
""" LaTeX Genealogy Tree adapter for Trees """
#-------------------------------------------------------------------------
#
# Standard Python modules
#
#-------------------------------------------------------------------------
from abc import ABCMeta, abstractmethod
import os
import logging

#-------------------------------------------------------------------------
#
# Gramps modules
#
#-------------------------------------------------------------------------
from ...const import GRAMPS_LOCALE as glocale
_ = glocale.translation.gettext

#-------------------------------------------------------------------------
#
# set up logging
#
#-------------------------------------------------------------------------
LOG = logging.getLogger(".treedoc")

#------------------------------------------------------------------------------
#
# TreeDoc
#
#------------------------------------------------------------------------------
class TreeDoc(metaclass=ABCMeta):
    """
    Abstract Interface for genealogy tree document generators. Output formats
    for genealogy tree reports must implement this interface to be used by the
    report system.
    """
    @abstractmethod
    def start_tree(self, option_list):
        """
        Write the start of a tree.
        """

    @abstractmethod
    def end_tree(self):
        """
        Write the end of a tree.
        """

    @abstractmethod
    def start_subgraph(self, level, subgraph_type, family, option_list=None):
        """
        Write the start of a subgraph.
        """

    @abstractmethod
    def end_subgraph(self, level):
        """
        Write the end of a subgraph.
        """

    @abstractmethod
    def write_node(self, db, level, node_type, person, marriage_flag,
                   option_list=None):
        """
        Write the contents of a node.
        """


