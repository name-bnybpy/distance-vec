import pandas as pd
from collections import defaultdict
#from IPython.display import clear_output

class Node:
    def __init__(self, name, connections):
        self.name = name
        self.direct = connections
        self.neighbours = {} #stores the routing tables of all its immediate neighbours, stored separately so in case of a connection cost change, it can still access this and calculate the correct new cost
        self.distance_table = defaultdict(lambda: defaultdict(int))

        conn_with_next = {}
        conn_no_next = {} #for sharing costs with other tables since the 'next' node is not necessary
        for conn in list(connections.keys()):
            conn_with_next[conn] = {'cost': connections[conn], 'next': conn}
            conn_no_next[conn] = connections[conn]
            self.distance_table[conn][conn] = connections[conn]
        self.cheapest = conn_with_next
        self.shared = conn_no_next

    def update_self(self, column=None): #returns whether the cheapest connections have updated, prompting a broadcast of the new costs from that node,
                                        #column param updates only that column while lack of it updates all columns, differentiating them for calculation efficiency
        if column: #updates distance table with current info
            missing_dests = []
            costs = self.neighbours[column]
            for dest in list(costs.keys()):
                if dest != self.name:
                    self.distance_table[column][dest] = costs[dest] + self.direct[column]
            for dest in list(self.distance_table[column].keys()):
                if dest not in list(costs.keys()):
                    missing_dests.append(dest)
            if column in missing_dests:
                missing_dests.remove(column)

            for dest in missing_dests:
                self.distance_table[column].pop(dest, None)
            
        else:
            for column in list(self.neighbours.keys()):
                if column != self.name:
                    missing_dests = []
                    costs = self.neighbours[column]

                    for dest in list(costs.keys()):
                        if dest != self.name:
                            self.distance_table[column][dest] = costs[dest] + self.direct[column]
                    for dest in list(self.distance_table[column].keys()):
                        if dest not in list(costs.keys()):
                            missing_dests.append(dest)
                    missing_dests.remove(column)
                    for dest in missing_dests:
                        self.distance_table[column].pop(dest, None)

        changed = False #finds min cost, returns true of min cost has changed
        all_rows = set()
        for rows in self.distance_table.values():
            all_rows.update(rows.keys())

        #print(self.distance_table)

        for row in all_rows:
            minval = {'cost': None, 'next': None}
            for column in self.distance_table.keys():
                value = self.distance_table[column].get(row, None)  # Use None or a default value if the row doesn't exist in the column
                if value:
                    if not minval['cost']:
                        minval = {'cost': value, 'next': column}
                    elif value < minval['cost']:
                        minval = {'cost': value, 'next': column} # if minval is none, I cry.

            if minval['cost'] > 1000: #Arbitrary upper bound, after which it is decided that node is unreachable. 
                                        #This is protection for when a connection fails
                changed = True
                if row in list(self.cheapest.keys()):
                    self.cheapest.pop(row, None) #removes node from its routing table
                    self.shared.pop(row, None)
                continue

            if row not in list(self.cheapest.keys()):
                self.cheapest[row] = minval
                self.shared[row] = minval['cost']
                changed = True
            elif minval['cost'] != self.cheapest[row]['cost']: #because the route to that point might be altered, so you have to check over all possible routes
                self.cheapest[row] = minval
                self.shared[row] = minval['cost']
                changed = True
        return changed

    def update_neighbours(self, source, connections):
        self.neighbours[source] = connections
        return self.update_self(column=source)

    def update_direct(self, connections):
        self.direct = connections
        for conn in list(connections.keys()):
            self.distance_table[conn][conn] = connections[conn]
        columns = list(self.distance_table.keys())
        cut_connection = []
        for col in columns:
            if col not in connections.keys():
                self.neighbours.pop(col, None) #removes stored distance vector of removed neighbour
                self.distance_table.pop(col, None) #removes column from distance table if no longer able to reach that node
        return self.update_self()

    def __str__(self):
        out = "Distance Table:\n"
        out += pd.DataFrame(self.distance_table).fillna('∞').to_string()
        out += "\nRouting Table:\n"
        out += (
                    f"{'Destination':<11}"
                    f"|{'Next':<5}"
                    f"|{'Cost':<5}\n"
               )
        for conn in list(self.cheapest.keys()):
            out += (
                        f"{conn:<11}"
                        f"|{self.cheapest[conn]['next']:<5}"
                        f"|{self.cheapest[conn]['cost']:<5d}\n"
                   )
        return out

    def get_distance_table(self):
        return pd.DataFrame(self.distance_table).fillna('∞')

    def get_routing_table(self):
        return pd.DataFrame(self.cheapest).T

class Cast:
    def __init__(self, source, destination, time, content):
        self.source = source
        self.destination = destination #Source and destination taken as node objects
        self.time = time #Time taken to reach the destination from the source
        self.content = content #contains the connections
    def elapse(self, time):
        self.time -= time

class State:
    def __init__(self, connections):
        print("INITIALISING")
        self.time_from_start = 0
        self.nodes = []
        for node in list(connections.keys()):
            new_node = Node(name=node, connections=connections[node])
            self.nodes.append(new_node)
        self.casts = [] #keeps track of broadcasts and their progress
        self.connections = connections
        #Some different format for inputting connections. Some init from defining all the base nodes. Keep track of broadcasts and their progress
    
    def run(self):
        for node in self.nodes:
            self.broadcast(node)

    def get_node_from_name(self, name):
        for node in self.nodes:
            if node.name == name:
                return node

    def tick(self, time=None): #ticks to the arrival of the next earliest cast
        #clear_output()
        to_broadcast = []
        received = []
        if not time:
            next_time = min(self.casts, key=lambda node: node.time).time #min time for the next broadcast to arrive
        else:
            next_time = time

        self.time_from_start += next_time
        to_remove = []
        for cast in self.casts:
            cast.elapse(next_time)
            if cast.time <= 0:
                if cast.destination not in received:
                    received.append(cast.destination)
                if cast.destination.update_neighbours(cast.source.name, cast.content):
                    if cast.destination not in to_broadcast:
                        to_broadcast.append(cast.destination)
                to_remove.append(cast)
        for cast in to_remove:
            self.casts.remove(cast)

        for node in to_broadcast:
            self.broadcast(node)

        return received, len(self.casts) == 0


    def broadcast(self, node): #shares information of the best costs to all immediate neighbours of the node
        for neighbour in list(node.direct.keys()):
            #print("BROADCAST:")
            self.casts.append(Cast(node, self.get_node_from_name(neighbour), node.direct[neighbour], node.shared.copy()))

    def print_state(self):
        print(f"Time from start: {self.time_from_start}")
        for node in self.nodes:
            print(f"NODE {node.name} INFORMATION:")
            print(node)

    def generate_graph_data(self):
        graph_data = {}
        graph_data['nodes'] = [{'id': node.name} for node in self.nodes]
        #print([node.name for node in self.nodes])
        #print("Why is there a loop here???")
        graph_data['links'] = []
        checked_nodes = []
        for node in self.nodes:
            for connection in node.direct.keys():
                if connection not in checked_nodes:
                    graph_data['links'].append({'source': node.name, 'target': connection, 'label': node.direct[connection]})
        graph_data['messages'] = []
        for cast in self.casts:
            cost = cast.source.direct[cast.destination.name]
            graph_data['messages'].append({'source': cast.source.name, 'target': cast.destination.name, 'progress': (cost - cast.time)/cost})
        return graph_data

    def generate_message_data(self):
        message_data = []
        for cast in self.casts:
            cost = cast.source.direct[cast.destination.name]
            message_data.append({'source': cast.source.name, 'target': cast.destination.name, 'progress': (cost - cast.time)/cost})
        return message_data

    def generate_routing_data(self):
        routing_data = {}
        for node in self.nodes:
            routing_data[node.name] = node.get_routing_table().to_dict()
        return routing_data

    def add_node(self):
        current_nodes = list(self.connections.keys())
        current_nodes.sort()
        print(current_nodes)
        if len(current_nodes) == 0:
            new_node_name = 'A'
        else:
            new_node_name = chr(ord(current_nodes[-1]) + 1)
        self.nodes.append(Node(name=new_node_name, connections={}))
        self.connections[new_node_name] = {}
        print([node.name for node in self.nodes])

    def remove_node(self, node_name):
        self.connections.pop(node_name, None)
        self.nodes.remove(self.get_node_from_name(node_name))
        for node in self.connections.keys():
            self.connections[node].pop(node_name, None)
        for node in self.nodes:
            if node.update_direct(self.connections[node.name]):
                self.broadcast(node)

    def edit_node(self, node_name, connections):
        for node in list(self.connections[node_name].keys()):
            self.connections[node].pop(node_name) #removes all neighbour references to edited node
        self.connections[node_name] = connections
        for node in list(connections.keys()):
            self.connections[node][node_name] = connections[node] #assigns new cost of path to all neighbour references
        for node in self.nodes:
            if node.update_direct(self.connections[node.name]):
                self.broadcast(node)
            

'''
graph_data = {
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
        {'source': 'A', 'target': 'B', 'progress': 0.5, 'id': 'msg1'},  # 50% along the link
        {'source': 'B', 'target': 'C', 'progress': 0.75, 'id': 'msg2'},  # 75% along the link
    ]
}
'''
