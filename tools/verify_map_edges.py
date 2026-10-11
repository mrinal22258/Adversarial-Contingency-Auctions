import os
import networkx as nx

graphml_path = "data/maps/boston_downtown_drive.graphml"
g = nx.read_graphml(graphml_path)
print("Boston downtown graphml:")
print("  Total nodes:", g.number_of_nodes())
print("  Total edges (nx.read_graphml):", g.number_of_edges())
print("  Is directed:", g.is_directed())

# Undirected view / multigraph check
if g.is_directed():
    ug = g.to_undirected()
    print("  Undirected nodes:", ug.number_of_nodes())
    print("  Undirected edges:", ug.number_of_edges())

# Connected components
comps = list(nx.connected_components(g.to_undirected()))
print("  Number of connected components:", len(comps))
largest_cc = max(comps, key=len)
print("  Largest component nodes:", len(largest_cc))
sub_g = ug.subgraph(largest_cc)
print("  Largest component edges:", sub_g.number_of_edges())
