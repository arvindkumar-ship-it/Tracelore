"use client";
import { useMemo } from "react";
import {
  ReactFlow,
  Background,
  Controls,
  MiniMap,
  MarkerType,
} from "@xyflow/react";
import dagre from "@dagrejs/dagre";
import "@xyflow/react/dist/style.css";
import type { Graph } from "@/lib/schemas";
export function CausalGraph({ value }: { value: Graph }) {
  const { nodes, edges } = useMemo(() => {
    const graph = new dagre.graphlib.Graph()
      .setGraph({ rankdir: "TB", nodesep: 55, ranksep: 90 })
      .setDefaultEdgeLabel(() => ({}));
    value.nodes.forEach((node) =>
      graph.setNode(node.id, { width: 190, height: 58 }),
    );
    value.edges.forEach((edge) => graph.setEdge(edge.source, edge.target));
    dagre.layout(graph);
    return {
      nodes: value.nodes.map((node) => ({
        id: node.id,
        position: {
          x: graph.node(node.id).x - 95,
          y: graph.node(node.id).y - 29,
        },
        data: {
          label: `${node.anomalous ? "! " : ""}${node.id}${node.root_candidate ? " · candidate" : ""}`,
        },
        style: {
          background: node.anomalous ? "#31232b" : "#162533",
          color: node.anomalous ? "#f5a3a7" : "#c8d8e7",
          border: `${node.root_candidate ? 2 : 1}px solid ${node.root_candidate ? "#b8ef86" : node.anomalous ? "#ba6975" : "#3d5669"}`,
          borderRadius: 8,
          width: 190,
          padding: 16,
          fontSize: 11,
        },
      })),
      edges: value.edges.map((edge, index) => ({
        id: `edge-${index}`,
        source: edge.source,
        target: edge.target,
        label: `${edge.calls} calls`,
        animated: edge.propagation,
        style: { stroke: edge.propagation ? "#b8ef86" : "#4e657b" },
        labelStyle: { fill: "#a4b6c8", fontSize: 9 },
        labelBgStyle: { fill: "#0d151f" },
        markerEnd: { type: MarkerType.ArrowClosed, color: "#5e7b92" },
      })),
    };
  }, [value]);
  return (
    <div className="graph-canvas">
      <ReactFlow
        nodes={nodes}
        edges={edges}
        fitView
        minZoom={0.2}
        maxZoom={2.5}
      >
        <Background color="#2b3b4d" gap={25} />
        <Controls />
        <MiniMap
          nodeColor={(node) =>
            node.style?.border?.toString().includes("b8ef86")
              ? "#b8ef86"
              : "#436177"
          }
          style={{ background: "#14202c" }}
        />
      </ReactFlow>
    </div>
  );
}
