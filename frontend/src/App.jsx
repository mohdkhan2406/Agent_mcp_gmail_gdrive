import { useState } from "react";

import "./App.css";

import logo from "./assets/logo.png";


function App() {

    const [query, setQuery] = useState("");

    const [answer, setAnswer] = useState("");

    const [loading, setLoading] = useState(false);


    const searchAgent = async () => {

        if (!query.trim()) {
            return;
        }

        setLoading(true);

        setAnswer("");

        try {

            const response = await fetch(
                "http://localhost:8000/query",
                {
                    method: "POST",

                    headers: {
                        "Content-Type": "application/json"
                    },

                    body: JSON.stringify({
                        query: query
                    })
                }
            );


            const data = await response.json();


            if (!response.ok) {

                throw new Error(
                    data.detail || "Request failed"
                );

            }


            setAnswer(data.answer);


        } catch (error) {

            setAnswer(
                "Unable to process your request. " +
                error.message
            );

        } finally {

            setLoading(false);

        }

    };


    const handleKeyDown = (event) => {

        if (
            event.key === "Enter" &&
            !event.shiftKey
        ) {

            event.preventDefault();

            searchAgent();

        }

    };


    const useExample = (text) => {

        setQuery(text);

        setAnswer("");

    };


    return (

        <div className="app">


            {/* =================================================
                BACKGROUND
            ================================================= */}

            <div className="background-glow glow-one"></div>

            <div className="background-glow glow-two"></div>



            {/* =================================================
                HEADER
            ================================================= */}

            <header className="header">


                <div className="brand">


                    <div className="logo-container">

                        <img
                            src={logo}
                            alt="VPro Skills"
                            className="logo"
                        />

                    </div>


                    <div className="brand-text">

                        <div className="brand-name">
                            VPro Skills
                        </div>

                        <div className="brand-subtitle">
                            EduTech • AI Engineering
                        </div>

                    </div>


                </div>



                <div className="workshop-badge">

                    <span className="live-dot"></span>

                    LIVE WORKSHOP

                </div>


            </header>



            {/* =================================================
                MAIN
            ================================================= */}

            <main className="main">


                {/* =================================================
                    HERO
                ================================================= */}

                <section className="hero">


                    <div className="eyebrow">

                        <span>AGENT DEVELOPMENT</span>

                        <span className="separator">/</span>

                        <span>HANDS-ON LAB</span>

                    </div>


                    <h1>

                        Agent Development
                        <span> Workshop</span>

                    </h1>


                    <p className="hero-description">

                        Build and interact with an AI Agent using
                        <strong> LLMs</strong>,
                        <strong> LangGraph</strong> and
                        <strong> MCP</strong>.

                    </p>


                </section>



                {/* =================================================
                    ARCHITECTURE
                ================================================= */}

                <section className="architecture">


                    <div className="architecture-line"></div>


                    <div className="architecture-item">

                        <div className="architecture-icon">
                            AI
                        </div>

                        <div className="architecture-text">

                            <strong>LLM</strong>

                            <span>Decision Maker</span>

                        </div>

                    </div>


                    <div className="architecture-arrow">
                        →
                    </div>


                    <div className="architecture-item active">

                        <div className="architecture-icon">
                            LG
                        </div>

                        <div className="architecture-text">

                            <strong>LangGraph</strong>

                            <span>Agent Workflow</span>

                        </div>

                    </div>


                    <div className="architecture-arrow">
                        →
                    </div>


                    <div className="architecture-item">

                        <div className="architecture-icon">
                            MCP
                        </div>

                        <div className="architecture-text">

                            <strong>MCP</strong>

                            <span>Tool Protocol</span>

                        </div>

                    </div>


                    <div className="architecture-arrow">
                        →
                    </div>


                    <div className="architecture-item">

                        <div className="architecture-icon">
                            ⚡
                        </div>

                        <div className="architecture-text">

                            <strong>Tools</strong>

                            <span>Gmail + Drive</span>

                        </div>

                    </div>


                </section>



                {/* =================================================
                    WORKSPACE
                ================================================= */}

                <section className="workspace">


                    {/* LEFT SIDE */}

                    <div className="workspace-left">


                        <div className="workspace-header">


                            <div>

                                <div className="workspace-label">
                                    AGENT CONSOLE
                                </div>

                                <h2>
                                    Ask your Agent
                                </h2>

                            </div>


                            <div className="online">

                                <span></span>

                                ONLINE

                            </div>


                        </div>



                        {/* QUERY */}

                        <div className="query-box">


                            <div className="query-top">


                                <span className="query-label">
                                    NATURAL LANGUAGE QUERY
                                </span>


                                <span className="shortcut">
                                    ENTER ↵
                                </span>


                            </div>


                            <textarea

                                value={query}

                                onChange={(event) =>
                                    setQuery(
                                        event.target.value
                                    )
                                }

                                onKeyDown={
                                    handleKeyDown
                                }

                                placeholder={
                                    "Ask the agent to search Gmail or Google Drive..."
                                }

                            />


                            <div className="query-footer">


                                <div className="connected-tools">


                                    <div className="tool-pill gmail">

                                        <span className="tool-symbol">
                                            ✉
                                        </span>

                                        Gmail

                                        <i></i>

                                    </div>


                                    <div className="tool-pill drive">

                                        <span className="tool-symbol">
                                            ◈
                                        </span>

                                        Google Drive

                                        <i></i>

                                    </div>


                                </div>



                                <button

                                    className="run-button"

                                    onClick={
                                        searchAgent
                                    }

                                    disabled={
                                        loading
                                    }

                                >

                                    {loading
                                        ? (
                                            <>
                                                <span className="button-spinner"></span>
                                                Running Agent
                                            </>
                                        )
                                        : (
                                            <>
                                                Run Agent
                                                <span className="button-arrow">
                                                    →
                                                </span>
                                            </>
                                        )
                                    }

                                </button>


                            </div>


                        </div>



                        {/* EXAMPLES */}

                        <div className="examples-section">


                            <div className="examples-title">

                                QUICK EXAMPLES

                            </div>


                            <div className="examples-grid">


                                <button
                                    onClick={() =>
                                        useExample(
                                            "Search email from mohd"
                                        )
                                    }
                                >

                                    <span className="example-icon">
                                        ✉
                                    </span>

                                    <span>

                                        <small>
                                            GMAIL
                                        </small>

                                        Search email from mohd

                                    </span>

                                    <b>→</b>

                                </button>



                                <button
                                    onClick={() =>
                                        useExample(
                                            "Search 3.png in Google Drive"
                                        )
                                    }
                                >

                                    <span className="example-icon">
                                        ◈
                                    </span>

                                    <span>

                                        <small>
                                            GOOGLE DRIVE
                                        </small>

                                        Search 3.png in Drive

                                    </span>

                                    <b>→</b>

                                </button>



                                <button
                                    onClick={() =>
                                        useExample(
                                            "Search my Gmail for Python course"
                                        )
                                    }
                                >

                                    <span className="example-icon">
                                        ✉
                                    </span>

                                    <span>

                                        <small>
                                            GMAIL
                                        </small>

                                        Find Python course emails

                                    </span>

                                    <b>→</b>

                                </button>



                                <button
                                    onClick={() =>
                                        useExample(
                                            "What is polymorphism in Python?"
                                        )
                                    }
                                >

                                    <span className="example-icon invalid">
                                        ×
                                    </span>

                                    <span>

                                        <small>
                                            INVALID CONTEXT
                                        </small>

                                        Test unsupported question

                                    </span>

                                    <b>→</b>

                                </button>


                            </div>


                        </div>


                    </div>



                    {/* RIGHT SIDE */}

                    <div className="workspace-right">


                        <div className="result-heading">


                            <div>

                                <div className="workspace-label">
                                    AGENT RESPONSE
                                </div>

                                <h2>
                                    Result
                                </h2>

                            </div>


                            {answer && !loading && (

                                <div className="success-badge">

                                    <span>✓</span>

                                    COMPLETED

                                </div>

                            )}


                        </div>



                        {!answer && !loading && (

                            <div className="empty-result">


                                <div className="empty-orbit">

                                    <div className="orbit-center">
                                        AI
                                    </div>

                                </div>


                                <h3>
                                    Ready for your query
                                </h3>


                                <p>

                                    Ask something about your
                                    Gmail or Google Drive.

                                </p>


                            </div>

                        )}



                        {loading && (

                            <div className="agent-running">


                                <div className="running-animation">

                                    <div></div>
                                    <div></div>
                                    <div></div>

                                </div>


                                <h3>
                                    Agent is thinking...
                                </h3>


                                <div className="execution-flow">

                                    <span className="completed">
                                        LLM
                                    </span>

                                    <b>→</b>

                                    <span className="completed">
                                        LangGraph
                                    </span>

                                    <b>→</b>

                                    <span className="active-flow">
                                        MCP
                                    </span>

                                    <b>→</b>

                                    <span>
                                        Tool
                                    </span>

                                </div>


                            </div>

                        )}



                        {answer && !loading && (

                            <div className="result-content">


                                <div className="result-meta">

                                    <span className="meta-dot"></span>

                                    Agent execution completed

                                </div>


                                <div className="answer-text">

                                    {answer}

                                </div>


                            </div>

                        )}


                    </div>


                </section>



                {/* =================================================
                    FOOTER STATS
                ================================================= */}

                <section className="stats">


                    <div>

                        <strong>
                            01
                        </strong>

                        <span>
                            LLM
                        </span>

                    </div>


                    <div className="stats-line"></div>


                    <div>

                        <strong>
                            01
                        </strong>

                        <span>
                            LangGraph
                        </span>

                    </div>


                    <div className="stats-line"></div>


                    <div>

                        <strong>
                            01
                        </strong>

                        <span>
                            MCP Server
                        </span>

                    </div>


                    <div className="stats-line"></div>


                    <div>

                        <strong>
                            02
                        </strong>

                        <span>
                            MCP Tools
                        </span>

                    </div>


                </section>


            </main>



            {/* =================================================
                FOOTER
            ================================================= */}

            <footer className="footer">

                <div>
                    VPro Skills EduTech
                </div>

                <div>
                    Agent Development Workshop
                </div>

                <div>
                    LLM • LangGraph • MCP
                </div>

            </footer>


        </div>

    );

}


export default App;