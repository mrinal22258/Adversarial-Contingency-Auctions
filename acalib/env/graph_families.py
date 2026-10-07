"""
Graph family generators for multi-robot navigation and task allocation:
1. Erdős–Rényi random graphs (ER)
2. Random Geometric Graphs (RGG)
3. Warehouse Grid topologies with picking aisles
"""

from typing import Dict, Tuple, Optional, Any
import numpy as np
import networkx as nx


def _ensure_connected(graph: nx.Graph, pos: Dict[Any, Tuple[float, float]], rng: np.random.Generator) -> nx.Graph:
    """Ensure the graph is connected by adding minimum-distance bridging edges between components."""
    if nx.is_connected(graph):
        return graph

    components = list(nx.connected_components(graph))
    while len(components) > 1:
        c1 = list(components[0])
        # Find closest pair between c1 and any other component
        best_u, best_v = None, None
        best_dist = float("inf")
        best_c_idx = -1

        for idx in range(1, len(components)):
            c2 = list(components[idx])
            for u in c1:
                p_u = np.array(pos[u])
                for v in c2:
                    p_v = np.array(pos[v])
                    d = float(np.linalg.norm(p_u - p_v))
                    if d < best_dist:
                        best_dist = d
                        best_u, best_v = u, v
                        best_c_idx = idx

        if best_u is not None and best_v is not None:
            graph.add_edge(best_u, best_v, weight=best_dist, length=best_dist)
            components[0] = components[0].union(components[best_c_idx])
            components.pop(best_c_idx)
        else:
            break

    return graph


def generate_erdos_renyi(
    n_nodes: int = 50,
    p: float = 0.12,
    seed: Optional[int] = None,
    scale: float = 100.0,
) -> nx.Graph:
    """
    Generate an Erdős–Rényi graph G(n, p) embedded in 2D space [0, scale] x [0, scale].
    Guaranteed to be connected.
    """
    rng = np.random.default_rng(seed)
    py_seed = int(rng.integers(0, 1000000))
    g = nx.erdos_renyi_graph(n_nodes, p, seed=py_seed)

    # Assign 2D positions
    pos = {i: (float(rng.uniform(0.0, scale)), float(rng.uniform(0.0, scale))) for i in g.nodes()}
    nx.set_node_attributes(g, pos, "pos")

    # Add weights as Euclidean distances
    for u, v in g.edges():
        pu = np.array(pos[u])
        pv = np.array(pos[v])
        dist = float(np.linalg.norm(pu - pv))
        g[u][v]["weight"] = max(0.1, dist)
        g[u][v]["length"] = max(0.1, dist)

    g = _ensure_connected(g, pos, rng)
    return g


def generate_random_geometric(
    n_nodes: int = 50,
    radius: Optional[float] = None,
    seed: Optional[int] = None,
    scale: float = 100.0,
) -> nx.Graph:
    """
    Generate a Random Geometric Graph (RGG) embedded in [0, scale] x [0, scale].
    If radius is not provided, uses connectivity threshold r_c ~ sqrt(log(n) / (pi * n)) * 1.5.
    Guaranteed connected.
    """
    rng = np.random.default_rng(seed)
    if radius is None:
        unit_rc = np.sqrt(np.log(max(2, n_nodes)) / (np.pi * n_nodes)) * 1.6
        radius = float(unit_rc * scale)

    py_seed = int(rng.integers(0, 1000000))
    g_unit = nx.random_geometric_graph(n_nodes, radius / scale, seed=py_seed)
    g = nx.Graph()
    g.add_nodes_from(g_unit.nodes())

    pos = {}
    for node, data in g_unit.nodes(data=True):
        ux, uy = data["pos"]
        pos[node] = (float(ux * scale), float(uy * scale))
    nx.set_node_attributes(g, pos, "pos")

    for u, v in g_unit.edges():
        pu = np.array(pos[u])
        pv = np.array(pos[v])
        dist = float(np.linalg.norm(pu - pv))
        g.add_edge(u, v, weight=max(0.1, dist), length=max(0.1, dist))

    g = _ensure_connected(g, pos, rng)
    return g


def generate_warehouse_grid(
    rows: int = 8,
    cols: int = 8,
    aisle_spacing: int = 2,
    seed: Optional[int] = None,
    cell_size: float = 12.5,
) -> nx.Graph:
    """
    Generate a warehouse grid graph with main cross-aisles and picking aisles.
    Obstacle shelves occupy between-aisle regions.
    Guaranteed connected.
    """
    rng = np.random.default_rng(seed)
    g = nx.Graph()
    node_id = 0
    grid_to_id = {}

    for r in range(rows):
        for c in range(cols):
            grid_to_id[(r, c)] = node_id
            pos = (float(c * cell_size), float(r * cell_size))
            g.add_node(node_id, pos=pos, grid_rc=(r, c))
            node_id += 1

    pos_dict = nx.get_node_attributes(g, "pos")

    # Add edges: horizontal cross-aisles always exist at top, bottom, and middle
    cross_aisle_rows = {0, rows - 1, rows // 2}

    for r in range(rows):
        for c in range(cols):
            curr_id = grid_to_id[(r, c)]

            # Horizontal connections: allow if in cross-aisle or probabilistic picking access
            if c + 1 < cols:
                right_id = grid_to_id[(r, c + 1)]
                if r in cross_aisle_rows or (c % aisle_spacing == 0):
                    g.add_edge(curr_id, right_id, weight=cell_size, length=cell_size)

            # Vertical connections: picking aisles along columns
            if r + 1 < rows:
                down_id = grid_to_id[(r + 1, c)]
                g.add_edge(curr_id, down_id, weight=cell_size, length=cell_size)

    g = _ensure_connected(g, pos_dict, rng)
    return g


def generate_graph(
    family: str = "rgg",
    n_nodes: int = 50,
    seed: Optional[int] = None,
    scale: float = 100.0,
    **kwargs: Any,
) -> nx.Graph:
    """
    Factory function for graph generation.
    family in {"er", "erdos_renyi", "rgg", "geometric", "warehouse", "grid"}
    """
    fam = family.lower()
    if fam in {"er", "erdos_renyi"}:
        p = kwargs.get("p", 0.12)
        return generate_erdos_renyi(n_nodes=n_nodes, p=p, seed=seed, scale=scale)
    elif fam in {"rgg", "geometric", "random_geometric"}:
        radius = kwargs.get("radius", None)
        return generate_random_geometric(n_nodes=n_nodes, radius=radius, seed=seed, scale=scale)
    elif fam in {"warehouse", "grid"}:
        # Calculate rows and cols to match approx n_nodes
        side = int(np.round(np.sqrt(n_nodes)))
        rows = kwargs.get("rows", max(3, side))
        cols = kwargs.get("cols", max(3, int(np.ceil(n_nodes / rows))))
        aisle_spacing = kwargs.get("aisle_spacing", 2)
        cell_size = scale / max(rows, cols)
        return generate_warehouse_grid(rows=rows, cols=cols, aisle_spacing=aisle_spacing, seed=seed, cell_size=cell_size)
    elif fam in {"warehouse_movingai", "movingai"}:
        from .real_maps import generate_movingai_warehouse
        return generate_movingai_warehouse(seed=seed, scale=scale, n_nodes=n_nodes)
    elif fam in {"road_osmnx", "osmnx", "road_network"}:
        from .real_maps import generate_real_road_network
        return generate_real_road_network(seed=seed, scale=scale)
    else:
        raise ValueError(f"Unknown graph family '{family}'. Choose from 'er', 'rgg', 'warehouse', 'warehouse_movingai', 'road_osmnx'.")
