import { Handle, useReactFlow } from "@xyflow/react";
import "./Nodes.css"
import { nodeTypes } from "./defaultNodes.ts";
import { useState } from "react";
import inputIcon from "../../assets/icons/input.svg";
import outputIcon from "../../assets/icons/output.svg";
import filterIcon from "../../assets/icons/filter.svg";
import aggrIcon from "../../assets/icons/aggr.svg";
import decodeIcon from "../../assets/icons/decode.svg";
import grayscaleIcon from "../../assets/icons/grayscale.svg";
import llmIcon from "../../assets/icons/llm.svg";
import resizeIcon from "../../assets/icons/resize.svg";
import windowIcon from "../../assets/icons/window.svg";

export function CircleNode({ label, icon, nodeDefinition }) {
    const foundType = nodeDefinition || nodeTypes.find(n => n.label.toLowerCase() === label.toLowerCase());
    const nodeIcon = getNodeIcon(label);
    const displayLabel = label && label.toLowerCase() === 'llm' ? label.toUpperCase() : label;

    return (
        <div className="circle-node">
            {nodeIcon ? (
                <img src={nodeIcon} width={30} height={30} alt={label} className="node-icon" />
            ) : (
                <i className={"fa-solid " + (foundType?.icon || icon)}></i>
            )}
            <div className="node-label">{displayLabel}</div>
        </div>

    )
}


function DescriptionNode({ label, id, nodeDefinition }) {
    const foundType = nodeDefinition || nodeTypes.find(n => n.label.toLowerCase() === label.toLowerCase());
    return (
        <div className="description-node">
            {foundType?.subtypes && foundType?.subtypes.length !== 0 &&
                <SelectSubtype node={foundType} subtypes={foundType.subtypes} id={id} />}
            {foundType?.info && <InfoBlock info={foundType.info} />}
            {foundType?.params && foundType?.params.length !== 0 &&
                <InputParamsNode id={id} params={foundType?.params} />}

        </div>
    )
}

// Icon mapping based on node labels
const iconMap = {
    'filter': filterIcon,
    'aggr': aggrIcon,
    'decode': decodeIcon,
    'grayscale': grayscaleIcon,
    'llm': llmIcon,
    'resize': resizeIcon,
    'window': windowIcon,
    'kafka source': inputIcon,
    'kafka sink': outputIcon,
    'source': inputIcon
};

function getNodeIcon(label) {
    // Use originalNodeType if available, otherwise fall back to label
    const key = label.toLowerCase();
    return iconMap[key] || null;
}

export default function FunctionNode({ data, id }) {
    const foundType = data.nodeDefinition || nodeTypes.find(n => n.label.toLowerCase() === data.label.toLowerCase());
    const {deleteElements} = useReactFlow();

    const handleDelete = () => {
        deleteElements({ nodes: [{ id: id }], edges: [] }).catch(e => console.log(e));
    };

    return (
        <div className="node-with-handlers">
            <button className="node-delete-btn" title="Delete node" onClick={handleDelete}>✕</button>
            <CircleNode id={id} label={data.label} nodeType={data.nodeType} icon={foundType?.icon} nodeDefinition={foundType} />
            <Handle
                type="source"
                position="right"
            />
            <Handle
                type="target"
                position="left"
            />
            <DescriptionNode label={data.label} id={id} nodeDefinition={foundType} />
        </div>
    );
}

export function BlockStartNode({ data, id }) {
    const nodeIcon = getNodeIcon(data.label);


    return (
        <div className="block-node" style={{ borderTopLeftRadius: 20, borderBottomLeftRadius: 20 }}>
            {nodeIcon ? (
                <img src={nodeIcon} width={30} height={30} alt={data.label} className="node-icon" />
            ) : (
                <i className={"fa-solid " + data.icon}></i>
            )}
            <div className="node-label">{data.label && data.label.toLowerCase() === 'llm' ? data.label.toUpperCase() : data.label}</div>

            <Handle
                type="source"
                position="right"
                style={{
                    position: 'absolute',
                }}
            />
            <DescriptionNode label={data.label} id={id} />
        </div>
    )
}

export function BlockEndNode({ data, id }) {
    const nodeIcon = getNodeIcon(data.label);

    return (
        <div className="block-node" style={{ borderTopRightRadius: 20, borderBottomRightRadius: 20 }}>
            {nodeIcon ? (
                <img src={nodeIcon} width={30} height={30} alt={data.label} className="node-icon" />
            ) : (
                <i className={"fa-solid " + data.icon}></i>
            )}
            <div className="node-label">{data.label && data.label.toLowerCase() === 'llm' ? data.label.toUpperCase() : data.label}</div>
            <Handle
                type="target"
                position="left"
                style={{
                    position: 'absolute'
                }} />
            <DescriptionNode label={data.label} id={id} />
        </div>
    )
}

function InputParamsNode({ id, params }) {
    return (
        <div className="input-params-node">
            <h4>Parameters</h4>
            {params?.map(param => (
                <div key={param.name}>
                    <label>{param.label}</label>
                    {param.isTextarea ? (
                        <textarea title={"Write your prompt"}
                            onChange={e => (e.currentTarget.title = e.currentTarget.value)}
                            id={param.id + "-" + id} rows={4} cols={30} />
                    ) : (
                        <input type={param.type} id={param.id + "-" + id} />
                    )}
                </div>
            ))}
        </div>
    );
}

function SelectSubtype({ node, subtypes, id }) {
    const defaultSubtype = subtypes && subtypes.length > 0 ? subtypes[0].subtype : "";
    const [selectedSubtype, setSelectedSubtype] = useState(defaultSubtype);

    const selectedSubtypeObj = subtypes?.find(option => option.subtype === selectedSubtype);

    return (
        <div>
            <h4>{node.label && node.label.toLowerCase() === 'llm' ? 'Model' : 'Subtype'}</h4>
            <select
                value={selectedSubtype}
                name="subtype-options"
                id={`subtype-select-${id}`}
                onChange={(e) => setSelectedSubtype(e.target.value)}
            >
                {subtypes?.map(option => (
                    <option key={option.subtype} value={option.subtype}>
                        {option.label}
                    </option>
                ))}
            </select>
            {selectedSubtypeObj?.params?.length > 0 && (
                <InputParamsNode id={id} params={selectedSubtypeObj.params} />
            )}
        </div>
    );
}

function InfoBlock({ info }) {
    return (
        <div>
            <h4>Information</h4>
            {info}
        </div>
    )
}