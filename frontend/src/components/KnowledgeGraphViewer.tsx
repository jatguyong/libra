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
    const upperType = type.toUpperCase();
    if (colorCache.has(upperType)) return colorCache.get(upperType)!;

    // Hardcoded special colors for different node types
    if (upperType === 'KBPEDIACONCEPT') {
        colorCache.set(upperType, '#5b83ad'); // Blue
        return '#5b83ad';
    }
    if (upperType === 'WIKIDATACONCEPT') {
        colorCache.set(upperType, '#45b583'); // Orange 
        return '#45b583';
    }
    if (upperType === 'DOCUMENTCHUNK') {
        colorCache.set(upperType, '#7a6f8f'); // Dark Purple Gray
        return '#7a6f8f';
    }
    if (upperType === 'KBPEDIACHUNK') {
        colorCache.set(upperType, '#e8a04c'); // Orange
        return '#e8a04c';
    }
    if (upperType === 'CHUNK') {
        colorCache.set(upperType, '#7a6f8f'); // Fallback for legacy Chunk label
        return '#7a6f8f';
    }
    if (upperType === 'DOCUMENT') {
        colorCache.set(upperType, '#8a6dc4ff'); // Medium Purple
        return '#8a6dc4ff';
    }

    const colors = [
        '#ba52a2', '#48589e', '#5b83ad', '#b56d45', '#45b583', '#854b8a', '#477d94', '#998d5c'
    ];
    const color = colors[colorCache.size % colors.length];
    colorCache.set(upperType, color);
    return color;
}

export default function KnowledgeGraphViewer({ isOpen, onClose, graphData }: KnowledgeGraphViewerProps) {
    const fgRef = useRef<any>(null);
    const containerRef = useRef<HTMLDivElement>(null);
    const [dimensions, setDimensions] = useState({ width: 800, height: 600 });
    const [selectedNode, setSelectedNode] = useState<any>(null);
    const [hoverNode, setHoverNode] = useState<any>(null);

    useEffect(() => {
        if (isOpen && containerRef.current) {
            setDimensions({
                width: containerRef.current.clientWidth,
                height: containerRef.current.clientHeight
            });
            // Enhance physics for better spacing
            if (fgRef.current) {
                fgRef.current.d3Force('charge').strength(-100);
                const linkForce = fgRef.current.d3Force('link');
                if (linkForce) linkForce.distance(120);
            }
            // Automatically zoom to fit when data loads
            if (graphData && graphData.nodes.length > 0) {
                setTimeout(() => {
                    fgRef.current?.zoomToFit(400, 50);
                }, 100);
            }
        }
    }, [isOpen, graphData]);


    const memoizedGraphData = useMemo(() => {
        if (!graphData) return { nodes: [], links: [] };

        const isChunkType = (label: string | undefined) =>
            label === 'DocumentChunk' || label === 'KBPediaChunk' || label === 'Chunk';

        const nodes = graphData.nodes.map(n => ({
            ...n,
            val: isChunkType(n.label) ? 15 : 25,
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
        <div className="fixed inset-0 z-[100] flex bg-black/60 backdrop-blur-md pointer-events-auto">
            <div className="w-full h-full flex bg-transparent relative">

                {/* Header / Close */}
                <button
                    onClick={() => {
                        console.log('Close button clicked');
                        setSelectedNode(null);
                        onClose();
                    }}
                    className="absolute top-6 right-6 z-10 w-10 h-10 flex items-center justify-center bg-white/5 hover:bg-white/10 text-white/70 hover:text-white rounded-full border border-white/10 transition-colors cursor-pointer backdrop-blur-md"
                    title="Close Visualization"
                >
                    <X size={20} />
                </button>

                {/* Main Graph Area */}
                <div className="flex-1 relative bg-transparent" ref={containerRef}>
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
                            nodeLabel={(node: any) => `
                            <div style="background: #1c1924; border: 1px solid #3d3d3d; border-radius: 6px; padding: 12px; font-family: Inter, sans-serif; pointer-events: none; margin-left: 15px;">
                                <span style="background: ${node.color || '#4ade80'}; color: #111; padding: 4px 12px; border-radius: 999px; font-size: 12px; font-weight: 600; display: inline-block; margin-bottom: 8px;">
                                    ${node.label || 'Unknown'}
                                </span>
                                <div style="font-size: 11px; text-transform: uppercase; font-weight: 700; color: #888; margin-bottom: 2px;">name</div>
                                <div style="font-size: 14px; font-weight: 500; color: #fff; max-width: 400px; overflow-wrap: break-word;">${node.name || node.id}</div>
                                ${node.description ? `<div style="font-size: 11px; text-transform: uppercase; font-weight: 700; color: #888; margin-top: 8px; margin-bottom: 2px;">description</div><div style="font-size: 12px; font-weight: 400; color: #ccc; max-width: 400px; overflow-wrap: break-word;">${node.description}</div>` : ''}
                            </div>
                        `}
                            nodeColor="color"
                            nodeRelSize={4}
                            linkDirectionalArrowLength={3.5}
                            linkDirectionalArrowRelPos={1}
                            linkColor="color"
                            linkCurvature={0.25}
                            linkCanvasObjectMode={() => 'after'}
                            linkCanvasObject={(link: any, ctx, globalScale) => {
                                const start = link.source;
                                const end = link.target;
                                if (typeof start !== 'object' || typeof end !== 'object') return;

                                // Hide link label if zoomed out far enough
                                if (globalScale < 0.8) return;

                                let textPos;
                                if (link.__controlPoints && link.__controlPoints.length === 2 && typeof link.__controlPoints[0] === 'number') {
                                    textPos = {
                                        x: 0.25 * start.x + 0.5 * link.__controlPoints[0] + 0.25 * end.x,
                                        y: 0.25 * start.y + 0.5 * link.__controlPoints[1] + 0.25 * end.y
                                    };
                                } else {
                                    textPos = {
                                        x: start.x + (end.x - start.x) / 2,
                                        y: start.y + (end.y - start.y) / 2
                                    };
                                }

                                const relLink = { x: end.x - start.x, y: end.y - start.y };
                                let angle = Math.atan2(relLink.y, relLink.x);

                                // Maintain label upright
                                if (angle > Math.PI / 2 || angle < -Math.PI / 2) {
                                    angle += Math.PI;
                                }

                                const label = link.name;
                                const fontSize = Math.max(10 / globalScale, 2);
                                ctx.font = `${fontSize}px Inter, sans-serif`;

                                const textWidth = ctx.measureText(label).width;
                                const bckgDimensions = [textWidth, fontSize].map(n => n + fontSize * 0.6);

                                ctx.save();
                                ctx.translate(textPos.x, textPos.y);
                                ctx.rotate(angle);

                                // Background pill
                                ctx.fillStyle = 'rgba(22, 17, 31, 0.9)';
                                ctx.beginPath();
                                if (typeof ctx.roundRect === 'function') {
                                    ctx.roundRect(-bckgDimensions[0] / 2, -bckgDimensions[1] / 2, bckgDimensions[0], bckgDimensions[1], bckgDimensions[1] / 2);
                                } else {
                                    ctx.fillRect(-bckgDimensions[0] / 2, -bckgDimensions[1] / 2, bckgDimensions[0], bckgDimensions[1]);
                                }
                                ctx.fill();
                                // Border
                                ctx.strokeStyle = 'rgba(255, 255, 255, 0.15)';
                                ctx.lineWidth = 1 / globalScale;
                                if (typeof ctx.roundRect === 'function') {
                                    ctx.stroke();
                                } else {
                                    ctx.strokeRect(-bckgDimensions[0] / 2, -bckgDimensions[1] / 2, bckgDimensions[0], bckgDimensions[1]);
                                }

                                // Text
                                ctx.textAlign = 'center';
                                ctx.textBaseline = 'middle';
                                ctx.fillStyle = '#d4d0dc';
                                ctx.fillText(label, 0, 0);

                                ctx.restore();
                            }}
                            onNodeClick={handleNodeClick}
                            onNodeHover={(node) => setHoverNode(node)}
                            nodeCanvasObject={(node: any, ctx, globalScale) => {
                                const label = node.name || node.id;
                                const fontSize = Math.max(12 / globalScale, 2);
                                const nodeR = Math.sqrt(Math.max(0, node.val || 1)) * 4;

                                // Draw circle fill
                                ctx.beginPath();
                                ctx.arc(node.x, node.y, nodeR, 0, 2 * Math.PI, false);
                                ctx.fillStyle = node.color || '#fff';
                                ctx.fill();

                                // Highlight selected / Hovered
                                const isSelectedOrHovered = (selectedNode && selectedNode.id === node.id) || (hoverNode && hoverNode.id === node.id);

                                if (isSelectedOrHovered) {
                                    // Inner dark border
                                    ctx.beginPath();
                                    ctx.arc(node.x, node.y, nodeR, 0, 2 * Math.PI, false);
                                    ctx.strokeStyle = '#222';
                                    ctx.lineWidth = 3 / globalScale;
                                    ctx.stroke();

                                    // Outer glowing neon border (matches fill)
                                    const neonColor = node.color || '#ba52a2';
                                    ctx.beginPath();
                                    ctx.arc(node.x, node.y, nodeR + 3 / globalScale, 0, 2 * Math.PI, false);
                                    ctx.strokeStyle = neonColor;
                                    ctx.lineWidth = 3 / globalScale;
                                    ctx.stroke();

                                    ctx.shadowColor = neonColor;
                                    ctx.shadowBlur = 15;
                                    ctx.stroke();
                                    ctx.shadowBlur = 0;
                                } else {
                                    // Default subtle border
                                    ctx.beginPath();
                                    ctx.arc(node.x, node.y, nodeR, 0, 2 * Math.PI, false);
                                    ctx.strokeStyle = 'rgba(0, 0, 0, 0.2)';
                                    ctx.lineWidth = 1.5 / globalScale;
                                    ctx.stroke();
                                }

                                // Draw text inside circle if zoomed in
                                if (globalScale >= 0.8) {
                                    ctx.font = `500 ${fontSize}px Inter, sans-serif`;
                                    // Conservative width for circle fit
                                    const maxWidth = nodeR * 1.5;
                                    const words = label.split(' ');
                                    let lines: string[] = [];
                                    let currentLine = words[0] || '';

                                    for (let i = 1; i < words.length; i++) {
                                        const word = words[i];
                                        const width = ctx.measureText(currentLine + " " + word).width;
                                        if (width < maxWidth) {
                                            currentLine += " " + word;
                                        } else {
                                            lines.push(currentLine);
                                            currentLine = word;
                                        }
                                    }
                                    if (currentLine) {
                                        lines.push(currentLine);
                                    }

                                    const formatLine = (line: string) => {
                                        let text = line;
                                        if (ctx.measureText(text).width > maxWidth) {
                                            while (ctx.measureText(text + "...").width > maxWidth && text.length > 0) {
                                                text = text.slice(0, -1);
                                            }
                                            return text + "...";
                                        }
                                        return text;
                                    };

                                    // Limit to 4 lines and format each
                                    if (lines.length > 4) {
                                        lines = [lines[0], lines[1], lines[2], lines[3] + "..."].map(formatLine);
                                    } else {
                                        lines = lines.map(formatLine);
                                    }

                                    ctx.textAlign = 'center';
                                    ctx.textBaseline = 'middle';
                                    ctx.fillStyle = '#ffffff';
                                    ctx.shadowColor = 'rgba(0,0,0,0.8)';
                                    ctx.shadowBlur = 4;

                                    const lineSpacing = 1.2;
                                    const startY = node.y - ((lines.length - 1) * fontSize * lineSpacing) / 2;

                                    lines.forEach((line, i) => {
                                        ctx.fillText(line, node.x, startY + i * fontSize * lineSpacing);
                                    });
                                }

                                // Reset shadow for next drawings
                                ctx.shadowBlur = 0;
                            }}
                        />
                    )}
                </div>

                {/* Sidebar Overview (Bloom Style) */}
                <div className="w-[320px] shrink-0 border-l border-white/10 bg-[#16111f] flex flex-col">
                    <div className="p-5 border-b border-white/5">
                        <div className="flex items-center justify-between">
                            <h2 className="text-white font-space font-medium tracking-wide flex items-center gap-2">
                                <Network size={18} className="text-white/50" />
                                Graph Overview
                            </h2>
                        </div>
                        <div className="mt-3 flex gap-4 text-xs font-mono text-white/60 uppercase">
                            <div>Nodes: <span className="text-white">{memoizedGraphData.nodes.length}</span></div>
                            <div>Edges: <span className="text-white">{memoizedGraphData.links.length}</span></div>
                        </div>
                    </div>

                    <div className="flex-1 overflow-y-auto p-5">
                        {selectedNode ? (
                            <div className="space-y-4">
                                <div className="flex items-center justify-between mb-4">
                                    <h3 className="text-sm font-semibold text-white/90">Node details</h3>
                                </div>

                                <div className="mt-2 inline-block px-3 py-1 rounded-full text-xs font-medium border"
                                    style={{
                                        backgroundColor: `${selectedNode.color}20`,
                                        color: selectedNode.color,
                                        borderColor: `${selectedNode.color}40`
                                    }}>
                                    {selectedNode.label || 'Node'}
                                </div>

                                <div className="w-full mt-4">
                                    <div className="grid grid-cols-[90px_1fr] border-b border-white/10 py-2">
                                        <div className="text-xs font-semibold text-white/50">Key</div>
                                        <div className="text-xs font-semibold text-white/50">Value</div>
                                    </div>

                                    {(selectedNode.name || selectedNode.id !== selectedNode.name) && (
                                        <div className="grid grid-cols-[90px_1fr] border-b border-white/5 py-2">
                                            <div className="text-xs font-mono text-white/90 font-bold">name</div>
                                            <div className="text-xs text-white/70 break-words">{selectedNode.name || selectedNode.id}</div>
                                        </div>
                                    )}

                                    {selectedNode.description && (
                                        <div className="grid grid-cols-[90px_1fr] border-b border-white/5 py-2">
                                            <div className="text-xs font-mono text-white/90 font-bold">definition</div>
                                            <div className="text-xs text-white/70 break-words max-h-96 overflow-y-auto">{selectedNode.description}</div>
                                        </div>
                                    )}

                                    {selectedNode.properties && Object.entries(selectedNode.properties).filter(([k]) => !['name', 'definition'].includes(k)).map(([key, val]) => (
                                        <div key={key} className="grid grid-cols-[90px_1fr] border-b border-white/5 py-2">
                                            <div className="text-xs font-mono text-white/90 font-bold break-words">{key}</div>
                                            <div className="text-xs text-white/70 break-words max-h-32 overflow-y-auto">
                                                {typeof val === 'object' ? JSON.stringify(val) : String(val)}
                                            </div>
                                        </div>
                                    ))}
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
                                            {graphData?.nodes.filter(n => n.label?.toUpperCase() === type).length || 0}
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
