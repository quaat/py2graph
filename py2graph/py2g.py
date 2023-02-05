import os
import json
from pydantic import BaseModel
from rdflib import Graph, URIRef, Literal, Namespace, BNode
from rdflib.namespace import XSD, OWL, RDF, RDFS

def get_properties(schema, objectName):
    assert 'title' in schema
    assert 'properties' in schema

    if not 'required' in schema:
        schema['required'] = []

    if objectName != schema['title']:
        assert 'definitions' in schema
        if objectName in schema['definitions']:
            schema = schema['definitions'][objectName]
        else:
            raise ValueError(f"Undefined object {objectName}")

    d = dict(title=schema['title'], properties=[])
    for prop in schema['properties']:
        isArray : bool = False
        isObject : bool = False
        isRequired: bool  =False

        if 'type' in schema['properties'][prop]:
            t = schema['properties'][prop]['type']
            isArray = (t == 'array')
            isRequired = (prop in schema['required'])
            if isArray and '$ref' in schema['properties'][prop]['items']:
                isObject = True
                hasType = os.path.basename(schema['properties'][prop]['items']['$ref'])
            elif isArray:
                isObject = False
                hasType = os.path.basename(schema['properties'][prop]['items']['type'])
            else:
                hasType = schema['properties'][prop]['format'] if 'format' in schema['properties'][prop] else schema['properties'][prop]['type']

        elif '$ref' in schema['properties'][prop]:
            isObject = True
            isRequired = (prop in schema['required'])
            hasType = os.path.basename(schema['properties'][prop]['$ref'])
        d['properties'].append(dict(prop=prop, isArray=isArray, isObject=isObject, isRequired=isRequired, hasType=hasType))
    return d

def get_data_properties(schema):
    for prop in schema['properties']:
        yield (prop, schema['properties'][prop])
        #yield (schema['properties'][prop])

def get_definitions(schema):
    if not 'definitions' in schema:
        return None
    for obj in schema['definitions']:
        yield (schema['definitions'][obj])

def get_objects(schema):
    if 'title' in schema and 'type' in schema and schema['type'] == 'object':
        yield (schema['title'])
    for definition in get_definitions(schema):
        if 'title' in definition and 'type' in definition and definition['type'] == 'object':
            yield (definition['title'])

def toType(pyType : str):
    rdftype = {
        'string':XSD.string,
        'integer':XSD.int,
        'date':XSD.dateTime
    }
    return rdftype[pyType] if pyType in rdftype else n[pyType]


def schema2graph(schema : BaseModel,
                 namespace : str = "http://www.onto-ns.com/1.0#",
                 fmt : str = 'turtle') -> str:

    ns = Namespace(namespace)
    g = Graph()
    g.bind("", ns)
    g.bind("rdf", RDF)
    g.bind("rdfs", RDFS)

    for obj in get_objects(schema):
        f = get_properties(schema, obj)
        g.add((ns[f['title']], RDF.type, OWL.Class))
        for p in f['properties']:
            if p['isObject']:
                g.add((ns[p['prop']], RDF.type, OWL.ObjectProperty))
            else:
                g.add((ns[p['prop']], RDF.type, OWL.DatatypeProperty))

            bnode = BNode()

            g.add((bnode, RDF.type, OWL.Restriction))
            g.add((bnode, OWL.onProperty, ns[p['prop']]))
            if p['isArray'] or (not p['isRequired']):
                g.add((bnode, OWL.someValuesFrom, toType(p['hasType'])))
            elif p['isRequired']:
                g.add((bnode,
                       OWL.qualifiedCardinality,
                       Literal(1, datatype=XSD.nonNegativeInteger)))
            if p['isObject']:
                g.add((bnode,
                       OWL.onClass,
                       toType(p['hasType'])))
            else:
                g.add((bnode,
                       OWL.onDataRange,
                       toType(p['hasType'])))

            g.add((ns[f['title']],RDFS.subClassOf, bnode))
    return (g.serialize(format=fmt))

def instance2graph(instance : BaseModel,
                   namespace : str = "http://www.onto-ns.com/1.0#",
                   fmt : str = 'turtle') -> str:

    ns = Namespace(namespace)
    graph = Graph()
    graph.bind("", ns)
    graph.bind("rdf", RDF)
    graph.bind("rdfs", RDFS)

    ns = Namespace(namespace)
    subj = ns[str(id(instance))]
    title = instance.schema()['title']

    graph.add((subj, RDF.type, OWL.NamedIndividual))
    graph.add((subj, RDF.type, ns[title]))

    for key, value in instance:
        if isinstance(value, BaseModel):
            obj = storeIndividual(graph, value)
            graph.add((subj, ns[key], obj))
        else:
            graph.add((subj, ns[key], Literal(value)))

    return (graph.serialize(format=fmt))
