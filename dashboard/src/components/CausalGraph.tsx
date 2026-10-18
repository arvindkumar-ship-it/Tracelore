"use client";
import { useMemo } from "react";
import {
  ReactFlow,
  Background,
  Controls,
  MiniMap,
  MarkerType,
  Position,
} from "@xyflow/react";
import dagre from "@dagrejs/dagre";
import "@xyflow/react/dist/style.css";
import type { Graph } from "@/lib/schemas";
import { Icon } from "./Icon";
export function CausalGraph({ value }: { value: Graph }) {
  const { nodes, edges } = useMemo(() => {
    const graph = new dagre.graphlib.Graph()
      .setGraph({ rankdir: "TB", nodesep: 65, ranksep: 95 })
      .setDefaultEdgeLabel(() => ({}));
    value.nodes.forEach((node) =>
      graph.setNode(node.id, { width: 206, height: 72 }),
    );
    value.edges.forEach((edge) => graph.setEdge(edge.source, edge.target));
    dagre.layout(graph);
    return {
      nodes: value.nodes.map((node) => ({
        id: node.id,
        initialWidth: 206,
        initialHeight: 72,
        position: {
          x: graph.node(node.id).x - 103,
          y: graph.node(node.id).y - 36,
        },
        sourcePosition: Position.Bottom,
        targetPosition: Position.Top,
        data: {
          label: (
            <div className="dependency-node">
              <span className="dependency-node-icon">
                <Icon
                  name={node.id.startsWith("db:") ? "database" : "server"}
                  size={17}
                />
              </span>
              <div>
                <strong>{node.id}</strong>
                <span>
                  {node.root_candidate
                    ? "Root candidate"
                    : node.anomalous
                      ? "Affected service"
                      : "Observed dependency"}
                </span>
              </div>
            </div>
          ),
        },
        className: `service-node ${node.anomalous ? "anomalous" : ""} ${node.root_candidate ? "root-candidate" : ""}`,
        style: { width: 206, minHeight: 72, padding: 14 },
      })),
      edges: value.edges.map((edge, index) => ({
        id: `edge-${index}`,
        source: edge.source,
        target: edge.target,
        label: `${edge.calls.toLocaleString()} calls`,
        style: {
          stroke: edge.propagation ? "#bd8064" : "#b7b2a8",
          strokeWidth: 1.4,
          strokeDasharray: edge.propagation ? "5 4" : undefined,
        },
        labelStyle: { fill: "#7c756a", fontSize: 10 },
        labelBgStyle: { fill: "#fbfaf7" },
        labelBgPadding: [6, 4] as [number, number],
        markerEnd: {
          type: MarkerType.ArrowClosed,
          color: edge.propagation ? "#bd8064" : "#b7b2a8",
        },
      })),
    };
  }, [value]);
  return (
    <div
      className="graph-canvas"
      role="region"
      aria-label="Service dependency graph"
    >
      <ReactFlow
        nodes={nodes}
        edges={edges}
        fitView
        fitViewOptions={{ padding: 0.25 }}
        minZoom={0.2}
        maxZoom={2.5}
      >
        <Background color="#dedad1" gap={24} size={1} />
        <Controls />
        <MiniMap
          position="top-right"
          pannable
          zoomable
          ariaLabel="Dependency map overview"
          nodeColor={(node) =>
            node.className?.includes("root-candidate")
              ? "#bc886e"
              : node.className?.includes("anomalous")
                ? "#c8b38a"
                : "#c4c3b9"
          }
          maskColor="rgb(245 243 237 / 65%)"
          style={{
            width: 140,
            height: 105,
            background: "#fbfaf7",
            border: "1px solid #e7e5df",
            borderRadius: 5,
          }}
        />
      </ReactFlow>
    </div>
  );
}
