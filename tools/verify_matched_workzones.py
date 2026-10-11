import sys
sys.path.insert(0, ".")
from acalib.env.real_maps import generate_real_road_network
from acalib.demo.render import get_boston_work_zone_edges

g = generate_real_road_network()
matched = get_boston_work_zone_edges(g)
print("Graph nodes:", g.number_of_nodes())
print("Graph edges:", g.number_of_edges())
print("Matched work zone edges:", len(matched))
