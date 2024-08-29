from flask import Flask, jsonify, redirect, url_for, render_template, request, session, flash
from model import State

app = Flask(__name__)

connections = { #default graph to be shown
                'A': {'B': 5, 'E': 1},
                'B': {'A': 5, 'D': 4},
                'C': {'E': 4},
                'D': {'B': 4, 'E': 2},
                'E': {'A': 1, 'C': 4, 'D': 2},
              }
sim = State(connections)
save_states = {}
logs = {} #logs the state of all routing tables over all times
node_logs = {} #logs changes to distance vec table and routing table over time of a specific node

graph_data = { # sample testing data
    "nodes": [
        {"id": "A"},
        {"id": "B"},
        {"id": "C"},
        {"id": "D"}
    ],
    "links": [
        {"source": "A", "target": "B", "label": "1"},
        {"source": "B", "target": "C", "label": "1"},
        {"source": "C", "target": "D", "label": "4"},
        {"source": "D", "target": "A", "label": "5"}
    ],
    'messages': [
        {'source': 'A', 'target': 'B', 'progress': 0.5},# 'id': 'msg1'},  # 50% along the link
        {'source': 'C', 'target': 'B', 'progress': 0.75},# 'id': 'msg2'},  # 75% along the link
    ]
}

@app.route('/')
def main():
    global sim
    sim = State(connections)
    test_data = sim.generate_graph_data()
    test_data['messages'] = []
    return render_template("main.html", graph=test_data)

@app.route('/run')
def run():
    global sim
    global save_states
    global logs
    global node_logs

    print("BEFORE")
    print(sim.time_from_start)
    sim.run()
    save_states[sim.time_from_start] = sim.generate_graph_data()
    logs[sim.time_from_start] = sim.generate_routing_data()
    for node in sim.nodes:
        if node.name not in list(node_logs.keys()):
            node_logs[node.name] = {sim.time_from_start: {'distance_table': node.get_distance_table().to_dict(), 'routing_table': node.get_routing_table().to_dict()}}
        else:
            node_logs[node.name][sim.time_from_start] = {'distance_table': node.get_distance_table().to_dict(), 'routing_table': node.get_routing_table().to_dict()}

    nodes, ended = sim.tick(0.5) # nodes should only update on integer times (only accepts integer costs) so this can be safely disregarded
    save_states[sim.time_from_start] = sim.generate_graph_data()
    logs[sim.time_from_start] = sim.generate_routing_data()
    while not ended:
        nodes, ended = sim.tick(0.5)
        save_states[sim.time_from_start] = sim.generate_graph_data()
        logs[sim.time_from_start] = sim.generate_routing_data()
        for node in nodes:
            node_logs[node.name][sim.time_from_start] = {'distance_table': node.get_distance_table().to_dict(), 'routing_table': node.get_routing_table().to_dict()}
        
        if sim.time_from_start >= 100: #hard limit for how far the sim goes
            break
    print(node_logs)
    save_states[sim.time_from_start] = sim.generate_graph_data()
    print("AFTER")
    print(sim.time_from_start)
    #print(node_logs)
    #print(logs)
    return jsonify({'max_value': sim.time_from_start, 'messages': save_states[0]['messages']})

@app.route('/reset')
def reset():
    global sim
    global save_states
    global logs
    global node_logs

    sim = State(connections)
    test_data = sim.generate_graph_data()
    test_data['messages'] = []
    save_states = {}
    logs = {}
    node_logs = {}
    print(test_data)
    return jsonify(test_data)

@app.route('/add_node')
def add_node():
    sim.add_node()
    test_data = sim.generate_graph_data()
    test_data['messages'] = []
    return jsonify(test_data)

@app.route('/remove_node', methods=['GET'])
def remove_node():
    node = str(request.args.get('name'))
    sim.remove_node(node)
    test_data = sim.generate_graph_data()
    test_data['messages'] = []
    return jsonify(test_data)

@app.route('/get_connection', methods=['GET'])
def get_connection():
    node = str(request.args.get('name'))
    connections = sim.connections
    connection = connections[node]
    data = {'cost': {}}
    for dest in list(connection.keys()):
        data['cost'][dest] = connection[dest] #wrap it in a dict because that's how the createTable function works
    print(data)
    return jsonify(data)

@app.route('/edit_node', methods=['POST'])
def edit_node():
    data = request.get_json()
    source = data['node']
    connections = data['connections']
    new_con = {}
    print(source, connections)
    for dest in list(connections.keys()):
        if dest.strip() != '':
            try:
                new_con[dest.strip()] = int(connections[dest]['cost'])
            except:
                return jsonify({'error': 'You can only enter integer costs!'}), 400
            if dest.strip() not in list(sim.connections.keys()):
                return jsonify({'error': 'Your destination nodes must be valid nodes on the graph!'}), 400
    if source in list(new_con.keys()):
        return jsonify({'error': 'You cannot link a node to itself!'}), 400 
    sim.edit_node(source, new_con)
    test_data = sim.generate_graph_data()
    test_data['messages'] = []
    print(test_data)
    return jsonify(test_data)

@app.route('/get_from_time',  methods=['GET'])
def get_from_time():
    global save_states
    # Get data from the POST request
    timestamp = float(request.args.get('timestamp'))
    graph = save_states[timestamp] #['messages']
    return jsonify(graph)

@app.route('/get_from_time_overview', methods=['GET'])
def get_from_time_overview():
    global logs
    timestamp = float(request.args.get('timestamp'))
    log = logs[timestamp]
    print(log)
    return jsonify(log)

@app.route('/get_node_logs')
def get_node_logs():
    global node_logs
    #print(node_logs)
    node_name = str(request.args.get('name'))
    log = node_logs[node_name]
    print(log)
    return jsonify(log)

@app.route('/data')
def data():
    return jsonify(graph_data)

if __name__ == '__main__':
    app.run(debug=True)