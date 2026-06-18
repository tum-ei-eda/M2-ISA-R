import networkx as nx
# G = nx.nx_agraph.read_dot("tree.dot")
G = nx.nx_agraph.read_dot("tree3.dot")
print("G", G)

label2group = {
    "Cores": 10,
    "Sets": 20,
    "Tree": 30,
    "Constants": 40,
    "Core": 50,
    "Functions": 60,
    "Memories": 70,
    "Memory Aliases": 80,
    "Instructions": 90,
    "Encoding": 100,
    "Assembly": 110,
    "Throws": 120,
    "Attributes": 130,
}
for node_id in G.nodes:
    n = G.nodes[node_id]
    label = n["label"]
    group = label2group.get(label)
    xlabel = n.get("xlabel")
    if group is None and xlabel is not None:
        group = label2group.get(xlabel)
    if xlabel:
        new_label = f"{xlabel}\n{label}"
        n["label"] = new_label
    print("label", label)
    print("xlabel", xlabel)
    print("group", group)
    n["title"] = "Test\nTest2"
    if group is not None:
        n["group"] = group

    print("n", n, dir(n))
# G = nx.cycle_graph(10)
# G.nodes[1]['title'] = 'Number 1'
# G.nodes[1]['group'] = 1
# G.nodes[3]['title'] = 'I belong to a different group!'
# G.nodes[3]['group'] = 10
# G.add_node(20, size=20, title='couple', group=2)
# G.add_node(21, size=15, title='couple', group=2)
# G.add_edge(20, 21, weight=5)
# G.add_node(25, size=25, label='lonely', title='lonely node', group=3)
from pyvis.network import Network
# nt = Network('1000px', '100%')
# nt = Network(height="1000px", width="100%", bgcolor="#222222", font_color="white", select_menu=True)
# nt = Network(height="1000px", width="100%", bgcolor="#222222", font_color="white", filter_menu=True)
# nt = Network(height="1000px", width="100%", bgcolor="#222222", font_color="white")
# nt = Network(height="500px", width="75%", bgcolor="#222222", font_color="white", directed=True)
nt = Network(height="1000px", width="100%", bgcolor="#222222", font_color="white", directed=True)
# nt = Network('600px', '100%')
# nt = Network('600px', '600px')
nt.from_nx(G)
# nt.show_buttons(filter_=['physics'])
nt.set_options("""
{
  "layout": {
    "hierarchical": {
      "enabled": true,
      "direction": "UD",
      "sortMethod": "directed"
    }
  },
  "physics": {
    "enabled": false
  }
}
""")
# nt.show_buttons()
nt.write_html("nx.html")
# nt.show("nx.html", notebook=False)
