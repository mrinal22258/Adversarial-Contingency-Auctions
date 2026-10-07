"""
Script to download real MovingAI MAPF warehouse maps and retrieve real OSMnx road network.
Outputs metadata including real SHA-256 hashes, source URLs, and retrieval dates.
"""
import os
import hashlib
import datetime
import urllib.request
import zipfile
import io
import json

def download_movingai_maps():
    os.makedirs("data/maps", exist_ok=True)
    url = "https://movingai.com/benchmarks/mapf/mapf-map.zip"
    req = urllib.request.Request(url, headers={"User-Agent": "Mozilla/5.0"})
    print(f"Downloading MovingAI maps from {url}...")
    with urllib.request.urlopen(req, timeout=30) as resp:
        data = resp.read()
    
    meta = {}
    access_date = datetime.date.today().isoformat()
    with zipfile.ZipFile(io.BytesIO(data)) as z:
        for target in ["warehouse-10-20-10-2-1.map", "warehouse-20-40-10-2-1.map"]:
            content = z.read(target)
            target_path = os.path.join("data", "maps", target)
            with open(target_path, "wb") as f:
                f.write(content)
            sha = hashlib.sha256(content).hexdigest()
            meta[target] = {
                "source_url": f"https://movingai.com/benchmarks/mapf/{target}",
                "archive_url": url,
                "access_date": access_date,
                "bytes": len(content),
                "sha256": sha,
            }
            print(f"Saved {target_path} ({len(content)} bytes, sha256: {sha})")
    return meta

def retrieve_osmnx_road_network():
    import osmnx as ox
    import networkx as nx
    
    os.makedirs("data/maps", exist_ok=True)
    # Downtown Boston bounding box: (north, south, east, west) or (bbox tuple in osmnx)
    # In osmnx 2.x bbox is (north, south, east, west) or bbox=(left, bottom, right, top)
    # Let's check ox.graph.graph_from_bbox signature:
    # In osmnx 2.0+, graph_from_bbox(bbox=(north, south, east, west)) or bbox=(bbox_tuple)
    # Let's inspect Downtown Boston: north=42.365, south=42.355, east=-71.055, west=-71.065
    access_date = datetime.date.today().isoformat()
    ox_version = ox.__version__
    print(f"Retrieving OSMnx road network using osmnx {ox_version}...")
    
    # Try bbox format
    # In osmnx 2.x, bbox is a 4-tuple: (north, south, east, west) or (west, south, east, north)
    # Let's test calling graph_from_bbox
    west, south, east, north = -71.065, 42.352, -71.050, 42.362
    print(f"Retrieving road network with bbox (left={west}, bottom={south}, right={east}, top={north})...")
    G = ox.graph_from_bbox(bbox=(west, south, east, north), network_type="drive", simplify=True)
        
    # Convert to undirected or largest strongly/weakly connected component
    G_undir = ox.convert.to_undirected(G) if hasattr(ox, "convert") else ox.to_undirected(G)
    largest_cc = max(nx.connected_components(G_undir), key=len)
    G_sub = G_undir.subgraph(largest_cc).copy()
    
    # Print node and edge count
    print(f"OSMnx graph retrieved: {len(G_sub.nodes())} nodes, {len(G_sub.edges())} edges")
    graphml_path = os.path.join("data", "maps", "boston_downtown_drive.graphml")
    
    # Save graphml
    ox.save_graphml(G_sub, filepath=graphml_path)
    
    with open(graphml_path, "rb") as f:
        graphml_bytes = f.read()
    sha = hashlib.sha256(graphml_bytes).hexdigest()
    
    meta = {
        "file": "boston_downtown_drive.graphml",
        "bbox": [north, south, east, west],
        "osmnx_version": ox_version,
        "access_date": access_date,
        "nodes": len(G_sub.nodes()),
        "edges": len(G_sub.edges()),
        "sha256": sha,
    }
    print(f"Saved {graphml_path} ({len(graphml_bytes)} bytes, sha256: {sha})")
    return meta

if __name__ == "__main__":
    maps_meta = download_movingai_maps()
    osmnx_meta = retrieve_osmnx_road_network()
    meta_path = os.path.join("data", "maps", "manifest.json")
    with open(meta_path, "w") as f:
        json.dump({"movingai": maps_meta, "osmnx": osmnx_meta}, f, indent=2)
    print(f"Wrote manifest to {meta_path}")
