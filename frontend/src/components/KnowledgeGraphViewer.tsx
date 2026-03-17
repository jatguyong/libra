import { useRef, useEffect, useState, useMemo, useCallback } from 'react';
import ForceGraph2D from 'react-force-graph-2d';
import { Network, X } from 'lucide-react';
import type { GraphData } from '../lib/types';

interface KnowledgeGraphViewerProps {
  isOpen: boolean;
  onClose: () => void;
  graphData: GraphData | null;
}

const colorCache = new Map<string, string>();

function getNodeColor(type: string): string {
  if (colorCache.has(type)) return colorCache.get(type)!;
  const colors = [
    '#f472b6', '#34d399', '#fbbf24', '#60a5fa', '#a78bfa',
    '#fb923c', '#2dd4bf', '#f87171', '#818cf8', '#38bdf8'
  ];
  const color = colors[colorCache.size % colors.length];
  colorCache.set(type, color);
  return color;
}

export default function KnowledgeGraphViewer({ isOpen, onClose, graphData }: KnowledgeGraphViewerProps) {
  const fgRef = useRef<any>(null);
  const containerRef = useRef<HTMLDivElement>(null);
  const [dimensions, setDimensions] = useState({ width: 800, height: 600 });
  const [selectedNode, setSelectedNode] = useState<any>(null);
  const [graphCounts, setGraphCounts] = useState<{ nodes: number, edges: number }>({ nodes: 0, edges: 0 });

  useEffect(() => {
    if (isOpen && containerRef.current) {
      setDimensions({
        width: containerRef.current.clientWidth,
        height: containerRef.current.clientHeight
      });
      // Automatically zoom to fit when data loads
      if (graphData && graphData.nodes.length > 0) {
        setGraphCounts({ nodes: graphData.nodes.length, edges: graphData.edges.length });
        setTimeout(() => {
           fgRef.current?.zoomToFit(400, 50);
        }, 100);
      }
    }
  }, [isOpen, graphData]);


  const memoizedGraphData = useMemo(() => {
    if (!graphData) return { nodes: [], links: [] };
    
    // Process formatting for react-force-graph
    const nodes = graphData.nodes.map(n => ({
        ...n,
        val: n.label === 'Chunk' ? 1.5 : 2.5,
        color: getNodeColor(n.label || 'Unknown')
    }));

    const links = graphData.edges.map(e => ({
        source: e.source,
        target: e.target,
        name: e.label || '',
        color: '#ffffff33'
    }));

    return { nodes, links };
  }, [graphData]);


  const handleNodeClick = useCallback((node: any) => {
    setSelectedNode(node);
    fgRef.current?.centerAt(node.x, node.y, 1000);
    fgRef.current?.zoom(4, 1000);
  }, []);

  if (!isOpen) return null;

  return (
    <div className="fixed inset-0 z-[100] flex items-center justify-center bg-black/80 backdrop-blur-sm p-8 pointer-events-auto">
        <div className="w-full h-full max-w-[1400px] flex bg-[#0E0915] border border-white/10 rounded-2xl shadow-2xl overflow-hidden relative">
            
            {/* Header / Close */}
            <button 
                onClick={() => { 
                    console.log('Close button clicked');
                    setSelectedNode(null); 
                    onClose(); 
                }} 
                className="absolute top-4 right-4 z-10 w-10 h-10 flex items-center justify-center bg-black/50 hover:bg-white/10 text-white rounded-full border border-white/10 transition-colors cursor-pointer"
                title="Close Visualization"
            >
                <X size={20} />
            </button>

            {/* Main Graph Area */}
            <div className="flex-1 relative bg-black/50" ref={containerRef}>
                 {!graphData || graphData.nodes.length === 0 ? (
                     <div className="absolute inset-0 flex flex-col items-center justify-center text-white/50">
                        <Network size={48} className="mb-4 opacity-50" />
                        <p>No knowledge graph data available for this query.</p>
                     </div>
                 ) : (
                     <ForceGraph2D
                        ref={fgRef}
                        width={dimensions.width}
                        height={dimensions.height}
                        graphData={memoizedGraphData}
                        nodeLabel="id"
                        nodeColor="color"
                        nodeRelSize={4}
                        linkDirectionalArrowLength={3.5}
                        linkDirectionalArrowRelPos={1}
                        linkColor="color"
                        linkCurvature={0.25}
                        linkLabel="name"
                        onNodeClick={handleNodeClick}
                        nodeCanvasObject={(node: any, ctx, globalScale) => {
                            const label = node.id;
                            const fontSize = Math.max(12 / globalScale, 2);
                            const nodeR = Math.sqrt(Math.max(0, node.val || 1)) * 4;
                            
                            // Draw circle
                            ctx.beginPath();
                            ctx.arc(node.x, node.y, nodeR, 0, 2 * Math.PI, false);
                            ctx.fillStyle = node.color || '#fff';
                            ctx.fill();

                            // Highlight selected
                            if (selectedNode && selectedNode.id === node.id) {
                                ctx.strokeStyle = 'white';
                                ctx.lineWidth = 1;
                                ctx.stroke();
                                ctx.shadowColor = 'white';
                                ctx.shadowBlur = 10;
                            } else {
                                ctx.shadowBlur = 0;
                            }

                            // Draw text
                            ctx.font = `${fontSize}px Inter, sans-serif`;
                            ctx.textAlign = 'center';
                            ctx.textBaseline = 'middle';
                            ctx.fillStyle = '#ffffffbb';
                            ctx.fillText(label, node.x, node.y + nodeR + (fontSize * 0.8));
                        }}
                     />
                 )}
            </div>

            {/* Sidebar Overview (Bloom Style) */}
            <div className="w-[320px] shrink-0 border-l border-white/10 bg-[#16111f] flex flex-col">
                <div className="p-5 border-b border-white/5">
                    <h2 className="text-white font-space font-medium tracking-wide flex items-center gap-2">
                        <Network size={18} className="text-white/50" />
                        Graph Overview
                    </h2>
                    <div className="mt-3 flex gap-4 text-xs font-mono text-white/60 uppercase">
                        <div>Nodes: <span className="text-white">{graphCounts.nodes}</span></div>
                        <div>Edges: <span className="text-white">{graphCounts.edges}</span></div>
                    </div>
                </div>

                <div className="flex-1 overflow-y-auto p-5">
                    {selectedNode ? (
                        <div className="space-y-4">
                            <h3 className="text-xs font-semibold uppercase tracking-wider text-white/40">Selected Node</h3>
                            
                            <div className="bg-white/5 rounded-lg border border-white/10 overflow-hidden">
                                <div className="px-3 py-2 bg-black/20 border-b border-white/5 flex items-center gap-2">
                                    <div className="w-3 h-3 rounded-full" style={{ backgroundColor: selectedNode.color }}></div>
                                    <span className="text-xs font-mono text-white/70 uppercase">{selectedNode.label}</span>
                                </div>
                                <div className="p-3">
                                    <p className="text-sm text-white/90 font-medium break-words">{selectedNode.id}</p>
                                </div>
                            </div>
                            
                            <button 
                                onClick={() => {
                                    setSelectedNode(null);
                                    fgRef.current?.zoomToFit(400, 50);
                                }}
                                className="text-xs text-cyan-400 hover:text-cyan-300 transition-colors"
                            >
                                Clear Selection
                            </button>
                        </div>
                    ) : (
                        <div className="space-y-4">
                            <h3 className="text-xs font-semibold uppercase tracking-wider text-white/40">Legend / Types</h3>
                            {Array.from(colorCache.entries()).map(([type, color]) => (
                                <div key={type} className="flex items-center justify-between p-2 rounded hover:bg-white/5 transition-colors cursor-default">
                                    <div className="flex items-center gap-3">
                                        <div className="w-4 h-4 rounded-full shadow-sm" style={{ backgroundColor: color }}></div>
                                        <span className="text-sm text-white/80 font-inter">{type}</span>
                                    </div>
                                    <span className="text-xs font-mono text-white/40">
                                        {graphData?.nodes.filter(n => n.label === type).length || 0}
                                    </span>
                                </div>
                            ))}
                            {colorCache.size === 0 && (
                                <p className="text-xs text-white/30 italic">No types mapped yet.</p>
                            )}
                        </div>
                    )}
                </div>
            </div>
        </div>
    </div>
  );
}
