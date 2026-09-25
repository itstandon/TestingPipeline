# Page 1

A Catalog of 30 Test Case Representations
Definitions, Structures, and Examples
Poojitha, Arushi, Brahma
Software Engineering Research Center
June 2026
Contents
1
Introduction
3
2
Gherkin (BDD DSL)
4
3
Use-Cases & User Stories
5
4
Goal-Oriented (KAOS / i*)
6
5
Natural Language -> DSL
7
6
Transition Systems (S, T, I)
8
7
Finite State Machines / Statecharts
9
8
Decision Tables
10
9
Cause-Effect Graph
11
10 Protocol State Machines
12
11 Sequence Diagrams
13
12 Interface Automata
14
13 xUnit Test Cases
15
14 Concolic Testing
16
15 Five-Structure Composite Model
17
16 Classification-Tree Method
18
17 Canonical Vector Space
19
18 Symbolic Path Conditions
20
19 Financial/Rule Tables
21
20 FSM Path-Based Representation
22
1


# Page 2

Summer Project 2026
Test Case Representations Catalog
21 The W Method
23
22 GUI Event Graphs
24
23 Object Construction Graphs
25
24 Domain-Specific DSLs
26
25 Test Requirement Matrix
27
26 Feature Vectors & Distributions
28
27 Consumer-Driven Contract
29
28 UML Testing Profile (UTP)
30
29 Petri Nets
31
30 Message Sequence Charts
32
31 Temporal Logic (LTL)
33
2


# Page 3

Summer Project 2026
Test Case Representations Catalog
1
Introduction
This document provides a comprehensive, structured catalog of the 30 test case representations
identified during the Systematic Literature Review (SLR) phase of our research. For each
representation, this catalog defines:
1. Literature Source: The primary paper, content location, and link.
2. Definition: The formal academic definition of the representation.
3. Structure: An explanation of how the representation is structured.
4. Example Requirement: The requirement used for demonstration (specifically Re-
quirement C from SRS section 9.2.1, detailing the 500ms command timeout ACK/NAK
protocol).
5. Example Test Case: A complete, syntax-accurate test case written in that specific
representation.
3


# Page 4

Summer Project 2026
Test Case Representations Catalog
2
Gherkin (BDD DSL)
• Primary Literature Source: Yinghao Chen et al. (A-TEST ’24)
• Content Location: Section II / Page 3
• Resource Link: Source Link
Definition
A structured, domain-specific language that uses natural language-like syntax to define software
behaviors and acceptance criteria in a human-readable format.
Structure of Representation
Uses structured, indentation-based keywords such as Feature, Background, Scenario, Given
(preconditions), When (actions), and Then (expected outcomes/assertions).
Example Requirement
The support structure for communicating commands must be reliable, with a uniform ACK/NAK
protocol adopted across all systems. Timeouts must be supported at approximately 500 msec.
Example Test Case
Feature: Command Communication Reliability
Scenario: Verification of 500ms Watchdog Timeout
Given the workstation is connected to the subsystem
And the subsystem status is in ’IDLE’ state
When the workstation sends a ’SELF_TEST’ command
And the subsystem fails to return a response within 500 milliseconds
Then the workstation should register a ’TIMEOUT_ERROR’ status
And the workstation should log the event as a warning
4


# Page 5

Summer Project 2026
Test Case Representations Catalog
3
Use-Cases & User Stories
• Primary Literature Source: Requirements-Based Testing (IEEE Access ’19)
• Content Location: Section III.B / Page 6
• Resource Link: Source Link
Definition
Natural language specifications that describe software requirements from either the actor’s
interaction path (Use Cases) or the user’s business goal (User Stories).
Structure of Representation
Use Cases define Actors, Triggers, Preconditions, Basic Flows, Alternate Flows, and Postcondi-
tions. User Stories follow the template: ’As a [Role], I want [Action] so that [Benefit].’
Example Requirement
The support structure for communicating commands must be reliable, with a uniform ACK/NAK
protocol adopted across all systems. Timeouts must be supported at approximately 500 msec.
Example Test Case
User Story:
As a Subsystem Controller
I want command communications to support a 500ms timeout
So that I can immediately detect network link failures.
Use Case Flow:
1. Actor: Workstation sends ’STATUS’ command to SUT.
2. SUT starts a 500ms watchdog timer.
3. SUT fails to receive an ACK response within 500ms.
4. Postcondition: SUT logs a Timeout Exception and resets the communication port.
5


# Page 6

Summer Project 2026
Test Case Representations Catalog
4
Goal-Oriented (KAOS / i*)
• Primary Literature Source: van Lamsweerde (Proc. IEEE RE ’01)
• Content Location: Section 3 / Page 4
• Resource Link: Source Link
Definition
A requirements engineering model that represents the relationship between system goals, opera-
tional tasks, agents, and obstacles to explain why a system behaves in a specific way.
Structure of Representation
KAOS maps Goals to Subgoals, and resolves obstacles using refinement trees. i* maps Strategic
Actors, Dependency links, Tasks, Resources, and Softgoals.
Example Requirement
The support structure for communicating commands must be reliable, with a uniform ACK/NAK
protocol adopted across all systems. Timeouts must be supported at approximately 500 msec.
Example Test Case
KAOS Goal Model Specification:
- Goal: Reliable Command Communication
- Subgoal: 500ms Timeout Detection
- Obstacle: Network Latency > 500ms
- Obstacle Resolution Test Case:
1. Setup: Inject 600ms latency on the communication line.
2. Action: Send ’VERSION’ command.
3. Assert: System triggers a timeout state rather than waiting indefinitely.
6


# Page 7

Summer Project 2026
Test Case Representations Catalog
5
Natural Language -> DSL
• Primary Literature Source: Zhiyi Xue et al. (LLM4Fin ’24)
• Content Location: Section III / Page 4
• Resource Link: Source Link
Definition
An intermediate representation that translates unstructured, ambiguous natural language re-
quirement texts into structured, programmatic logic clauses.
Structure of Representation
Represented as condition-action triplets, typically formatted as: PRECONDITION: [State
properties], ACTION: [Operational events], and POSTCONDITION: [Expected state properties].
Example Requirement
The support structure for communicating commands must be reliable, with a uniform ACK/NAK
protocol adopted across all systems. Timeouts must be supported at approximately 500 msec.
Example Test Case
PRECONDITION: connection_active(subsystem) == True AND command_sent == ’INITIALIZE’
ACTION: await_response_timer(500)
POSTCONDITION: elapsed_time >= 500 AND received_response == None AND system_verdict == TIMEO
7


# Page 8

Summer Project 2026
Test Case Representations Catalog
6
Transition Systems (S, T, I)
• Primary Literature Source: Bruno D. Miranda et al. (ACM TOCS ’23)
• Content Location: Section 3.1 / Page 5
• Resource Link: Source Link
Definition
A formal mathematical state machine representation that models execution traces as state
changes driven by event labels.
Structure of Representation
Defined as a tuple (S, T, I) where S is the set of states, T is the transition relation (S x Input
Label -> S), and I is the initial state.
Example Requirement
The support structure for communicating commands must be reliable, with a uniform ACK/NAK
protocol adopted across all systems. Timeouts must be supported at approximately 500 msec.
Example Test Case
Transition System (S, T, I) for Timeout Verification:
- States S = {Idle, CmdSent, AckReceived, NakReceived, TimeoutState}
- Initial State I = {Idle}
- Event Labels = {send_cmd, recv_ACK, recv_NAK, t_elapsed >= 500ms}
- Transition Relations T:
* (Idle, send_cmd, CmdSent)
* (CmdSent, recv_ACK, AckReceived)
* (CmdSent, recv_NAK, NakReceived)
* (CmdSent, t_elapsed >= 500ms, TimeoutState)
8


# Page 9

Summer Project 2026
Test Case Representations Catalog
7
Finite State Machines / Statecharts
• Primary Literature Source: Vaclav Rechtberger et al. (IEEE ICSTW ’22)
• Content Location: Section II / Page 2
• Resource Link: Source Link
Definition
A behavioral model composed of states, transitions, and actions. Statecharts extend FSMs by
adding nesting (hierarchy) and concurrency (parallel regions).
Structure of Representation
Usually represented as a State Transition Table mapping (Current State, Input) to (Next State,
Output), or visually as a state transition diagram.
Example Requirement
The support structure for communicating commands must be reliable, with a uniform ACK/NAK
protocol adopted across all systems. Timeouts must be supported at approximately 500 msec.
Example Test Case
FSM State Transition Table Rows:
+---------------+---------------+-------------------+--------------+
| Current State | Input Event
| Next State
| Output Action|
+---------------+---------------+-------------------+--------------+
| Idle
| send_command
| AwaitingResponse
| StartTimer
|
| AwaitingResp
| recv_ACK
| Idle
| StopTimer
|
| AwaitingResp
| recv_NAK
| Idle
| LogNakError
|
| AwaitingResp
| timer_expired | TimeoutState
| LogTimeout
|
+---------------+---------------+-------------------+--------------+
9


# Page 10

Summer Project 2026
Test Case Representations Catalog
8
Decision Tables
• Primary Literature Source: Decision Table Testing (IEEE TSE ’87)
• Content Location: Section II / Page 3
• Resource Link: Source Link
Definition
A tabular representation that maps combinations of boolean conditions to expected outcomes,
verifying logical business rules.
Structure of Representation
A grid divided into Condition Stubs (upper rows) and Action Stubs (lower rows), where each
column represents a unique combination rule.
Example Requirement
The support structure for communicating commands must be reliable, with a uniform ACK/NAK
protocol adopted across all systems. Timeouts must be supported at approximately 500 msec.
Example Test Case
Decision Table for Command Execution:
=========================================
Conditions:
- Command Dispatched
| Y | Y | Y | N |
- Response Received
| Y | Y | N | - |
- Response Type
|ACK|NAK| - | - |
- Elapsed Time < 500ms
| Y | Y | N | - |
=========================================
Actions:
- Commit Transaction
| X | - | - | - |
- Log Protocol Error
| - | X | - | - |
- Raise Timeout Exception | - | - | X | - |
- Retain IDLE State
| - | - | - | X |
=========================================
10


# Page 11

Summer Project 2026
Test Case Representations Catalog
9
Cause-Effect Graph
• Primary Literature Source: W. R. Elmendorf (IEEE TSE ’69)
• Content Location: Page 2
• Resource Link: Source Link
Definition
A directed graph representing boolean relationships between input conditions (causes) and
output actions (effects), used to derive test combinations.
Structure of Representation
Nodes representing causes (inputs) and effects (outputs) connected by logical operators (AND,
OR, NOT) and constraint lines.
Example Requirement
The support structure for communicating commands must be reliable, with a uniform ACK/NAK
protocol adopted across all systems. Timeouts must be supported at approximately 500 msec.
Example Test Case
Causes (Inputs):
- C1: Command Sent
- C2: ACK Received
- C3: NAK Received
- C4: Timeout Exceeded 500ms
Effects (Outputs):
- E1: Success registered (requires C1 AND C2)
- E2: Protocol Error logged (requires C1 AND C3)
- E3: Timeout raised (requires C1 AND C4)
Constraints:
- Exclusive (C2, C3, C4) : Only one response type can occur.
11


# Page 12

Summer Project 2026
Test Case Representations Catalog
10
Protocol State Machines
• Primary Literature Source: PSM Testing (IEEE ICSTW ’18)
• Content Location: Section III.C
• Resource Link: Source Link
Definition
A state machine that specifies the legal sequences of messages, commands, or events that can be
exchanged between components.
Structure of Representation
A state machine where transitions represent message exchanges (inputs/outputs) rather than
internal state changes.
Example Requirement
The support structure for communicating commands must be reliable, with a uniform ACK/NAK
protocol adopted across all systems. Timeouts must be supported at approximately 500 msec.
Example Test Case
Protocol Rules:
1. A command request must be followed by ACK, NAK, or Timeout.
2. Sending another command before receiving an ACK/NAK/Timeout violates the protocol.
Transitions:
- State: IDLE -- write_command --> WAITING
- State: WAITING -- read_ACK --> IDLE
- State: WAITING -- read_NAK --> IDLE
- State: WAITING -- timeout(500) --> IDLE (Action: Raise Timeout Alert)
12


# Page 13

Summer Project 2026
Test Case Representations Catalog
11
Sequence Diagrams
• Primary Literature Source: UML Sequence Diagrams Survey
• Content Location: Section IV
• Resource Link: Source Link
Definition
A UML interaction diagram that models the chronological exchange of messages between lifelines
of components.
Structure of Representation
Vertical lifelines represent system entities, while horizontal arrows represent synchronous or
asynchronous message calls, returns, and timers.
Example Requirement
The support structure for communicating commands must be reliable, with a uniform ACK/NAK
protocol adopted across all systems. Timeouts must be supported at approximately 500 msec.
Example Test Case
Sequence Flow Representation:
Workstation
Subsystem
|
|
|--- sendCmd(’STATUS’) ---->|
|
| [Start 500ms Timer]
|
|
| [Timer Exceeds 500ms]
|
| (Subsystem Silent)
|
|
|
|<-- (No Response) ---------|
|
|
[Raise Timeout Error]
|
13


# Page 14

Summer Project 2026
Test Case Representations Catalog
12
Interface Automata
• Primary Literature Source: L. de Alfaro et al. (Proc. ACM FSE ’01)
• Content Location: Section 2 / Page 3
• Resource Link: Source Link
Definition
A formal model used to verify software component compatibility by modeling communication
interfaces.
Structure of Representation
States connected by transitions categorized as inputs (denoted with ’?’), outputs (denoted with
’!’), or internal actions (denoted with ’;’).
Example Requirement
The support structure for communicating commands must be reliable, with a uniform ACK/NAK
protocol adopted across all systems. Timeouts must be supported at approximately 500 msec.
Example Test Case
Workstation Automaton:
- States: {Idle, Awaiting}
- Transitions:
* Idle -- cmd_sent! --> Awaiting
* Awaiting -- ACK? --> Idle
* Awaiting -- NAK? --> Idle
* Awaiting -- timeout? --> Idle
Subsystem Automaton:
- States: {Idle, Processing}
- Transitions:
* Idle -- cmd_sent? --> Processing
* Processing -- ACK! --> Idle
* Processing -- NAK! --> Idle
14


# Page 15

Summer Project 2026
Test Case Representations Catalog
13
xUnit Test Cases
• Primary Literature Source: ChatUniTest (ISSTA Companion ’25)
• Content Location: Section III
• Resource Link: Source Link
Definition
Executable source code blocks containing setup variables, method invocations, and assertions to
verify unit correctness.
Structure of Representation
Follows the Arrange-Act-Assert pattern. Setup code prepares SUT, execution runs methods,
and assertions verify outcomes.
Example Requirement
The support structure for communicating commands must be reliable, with a uniform ACK/NAK
protocol adopted across all systems. Timeouts must be supported at approximately 500 msec.
Example Test Case
@Test(timeout = 600)
public void testCommandTimeoutProtocol() {
CommandSender sender = new CommandSender("TelescopeSubsystem");
long startTime = System.currentTimeMillis();
Response res = sender.sendCommand("SELF_TEST");
long duration = System.currentTimeMillis() - startTime;
if (res == null) {
assertTrue("Timeout must happen at ~500ms", duration >= 500);
} else {
assertTrue("Response received in time", duration < 500);
assertTrue(res.isAck() || res.isNak());
}
}
15


# Page 16

Summer Project 2026
Test Case Representations Catalog
14
Concolic Testing
• Primary Literature Source: P. Godefroid et al. (Proc. ACM PLDI ’05)
• Content Location: Section 2
• Resource Link: Source Link
Definition
A hybrid testing method that pairs concrete execution with symbolic path analysis to systemati-
cally cover execution paths.
Structure of Representation
Co-execution of concrete inputs alongside symbolic path ledgers. Path constraints are inverted
and solved to generate new inputs.
Example Requirement
The support structure for communicating commands must be reliable, with a uniform ACK/NAK
protocol adopted across all systems. Timeouts must be supported at approximately 500 msec.
Example Test Case
1. Concrete Run: sendCommand("TEST", delay = 100ms) -> Path condition: delay < 500
2. Invert Constraint: delay >= 500
3. SMT Solver generates input: mock_network_delay = 501ms
4. Second Run: Concrete execution with 501ms delay triggers the timeout exception path.
16


# Page 17

Summer Project 2026
Test Case Representations Catalog
15
Five-Structure Composite Model
• Primary Literature Source: Structured Test Case Definition (IEEE Access ’20)
• Content Location: Section III / Page 5
• Resource Link: Source Link
Definition
A structured method that decomposes a test case into five distinct structural areas representing
the test lifecycle.
Structure of Representation
1. TC Factors (Setup) — 2. Internal Flow (Execution) — 3. Dynamic Interactions (API/Mocks)
— 4. Verification Calls (Oracles) — 5. Output & Results (Logs).
Example Requirement
The support structure for communicating commands must be reliable, with a uniform ACK/NAK
protocol adopted across all systems. Timeouts must be supported at approximately 500 msec.
Example Test Case
- TC Factors: Target IP = 192.168.1.5, Watchdog Timeout = 500ms.
- Internal Flow: Initialize socket, call send_command("STATUS").
- Dynamic Interactions: Mock network delay to 550ms.
- Verification Calls: assertResult(res == null), assertTimeElapsed(duration >= 500).
- Output: Write "TC_TIMEOUT_01: PASSED" to system test log.
17


# Page 18

Summer Project 2026
Test Case Representations Catalog
16
Classification-Tree Method
• Primary Literature Source: Classification Tree Method (IEEE Software ’93)
• Content Location: Section 2 / Page 4
• Resource Link: Source Link
Definition
A black-box test design technique that partitions the input space into disjoint equivalence classes
using a tree structure.
Structure of Representation
A tree of Classifications (aspects) and Classes (values), combined with a grid indicating combi-
nations representing test cases.
Example Requirement
The support structure for communicating commands must be reliable, with a uniform ACK/NAK
protocol adopted across all systems. Timeouts must be supported at approximately 500 msec.
Example Test Case
Classifications & Classes:
- Command Type: [Valid, Invalid]
- Response Delivery: [Instant, Delayed, Silent]
- Delayed Time: [<500ms, >=500ms]
Combinations Grid (Test Case 1):
- Command Type = Valid
- Response Delivery = Delayed
- Delayed Time = >=500ms
- Expected Outcome = Timeout Exception raised
18


# Page 19

Summer Project 2026
Test Case Representations Catalog
17
Canonical Vector Space
• Primary Literature Source: Bruno D. Miranda et al. (ACM TOCS ’23)
• Content Location: Section 4 / Page 8
• Resource Link: Source Link
Definition
A mathematical vector representation designed to model concurrent memory and execution
actions to detect race conditions.
Structure of Representation
Encoded as a multidimensional vector mapping operations, threads, memory locations, cache
states, and ordering relations.
Example Requirement
The support structure for communicating commands must be reliable, with a uniform ACK/NAK
protocol adopted across all systems. Timeouts must be supported at approximately 500 msec.
Example Test Case
Vector e = (Thread_A, Thread_B, Memory_Port, Op_Write, Op_Read, Collision)
- Thread_A: Dispatches command (Write action on Port)
- Thread_B: Monitors timeout timer (Read/Write action on Port)
- Memory_Port: Shared memory address
- Relation: Collision / Competition on timeout boundary at t = 500ms.
19


# Page 20

Summer Project 2026
Test Case Representations Catalog
18
Symbolic Path Conditions
• Primary Literature Source: Sarfraz Khurshid et al. (ISSE ’14)
• Content Location: Section 3
• Resource Link: Source Link
Definition
Mathematical constraints accumulated during symbolic execution representing program execution
paths.
Structure of Representation
A logical conjunction of inequalities and equalities over symbolic variables, solved using an SMT
solver.
Example Requirement
The support structure for communicating commands must be reliable, with a uniform ACK/NAK
protocol adopted across all systems. Timeouts must be supported at approximately 500 msec.
Example Test Case
Path Condition for Timeout Failure:
(sender.status == ’WAITING_FOR_ACK’) AND
(watchdog.timer_ms >= 500) AND
(incoming_buffer.length == 0)
20


# Page 21

Summer Project 2026
Test Case Representations Catalog
19
Financial/Rule Tables
• Primary Literature Source: Zhiyi Xue et al. (LLM4Fin ’24)
• Content Location: Section IV
• Resource Link: Source Link
Definition
Logical tables translating raw business rules into conditional executable statements.
Structure of Representation
A structure of logical rules matching inputs to constraints: IF [Inputs] AND [Constraints] THEN
[Action].
Example Requirement
The support structure for communicating commands must be reliable, with a uniform ACK/NAK
protocol adopted across all systems. Timeouts must be supported at approximately 500 msec.
Example Test Case
Rule Table:
- Rule 1: IF cmd_sent == True AND delay < 500 AND response == ACK THEN status = SUCCESS
- Rule 2: IF cmd_sent == True AND delay < 500 AND response == NAK THEN status = REJECTED
- Rule 3: IF cmd_sent == True AND delay >= 500 THEN status = TIMEOUT_ERROR
21


# Page 22

Summer Project 2026
Test Case Representations Catalog
20
FSM Path-Based Representation
• Primary Literature Source: Vaclav Rechtberger et al. (IEEE ICSTW ’22)
• Content Location: Section II.A
• Resource Link: Source Link
Definition
A test suite representation where test cases are defined as traversal paths through a state
transition graph.
Structure of Representation
Sequences of states and transitions classified under coverage metrics (e.g. Node, Edge, or Prime
Path).
Example Requirement
The support structure for communicating commands must be reliable, with a uniform ACK/NAK
protocol adopted across all systems. Timeouts must be supported at approximately 500 msec.
Example Test Case
Paths on FSM Graph G:
- Prime Path 1: Idle -> CmdSent -> AckReceived (Success)
- Prime Path 2: Idle -> CmdSent -> TimeoutState (Watchdog expired)
- Round Trip: Idle -> CmdSent -> AckReceived -> Idle
22


# Page 23

Summer Project 2026
Test Case Representations Catalog
21
The W Method
• Primary Literature Source: Vaclav Rechtberger et al. (IEEE ICSTW ’22)
• Content Location: Section II.B
• Resource Link: Source Link
Definition
A formal testing method for FSMs that guarantees complete error detection by using a transition
cover and a characterization set.
Structure of Representation
Concatenation of two sets of sequences: P (transition cover tree to reach all states) and W
(characterization set to distinguish states).
Example Requirement
The support structure for communicating commands must be reliable, with a uniform ACK/NAK
protocol adopted across all systems. Timeouts must be supported at approximately 500 msec.
Example Test Case
- Transition Cover P: {send_cmd} (reaches state ’AwaitingResponse’)
- Characterization Set W: {wait_500ms} (distinguishes ’AwaitingResponse’ by producing ’timeo
- Test sequence: P . W = {send_cmd, wait_500ms}
23


# Page 24

Summer Project 2026
Test Case Representations Catalog
22
GUI Event Graphs
• Primary Literature Source: Event-Flow Graphs (IEEE TSE ’05)
• Content Location: Section III / Page 4
• Resource Link: Source Link
Definition
A directed graph modeling sequences of UI events and window/component interactions.
Structure of Representation
Nodes represent UI actions (clicks, inputs) and edges represent structural flows or modal
dependency bounds.
Example Requirement
The support structure for communicating commands must be reliable, with a uniform ACK/NAK
protocol adopted across all systems. Timeouts must be supported at approximately 500 msec.
Example Test Case
Event Flow Graph Path:
Click ’Send Command’ -> disables input fields -> starts 500ms progress bar -> if response
24


# Page 25

Summer Project 2026
Test Case Representations Catalog
23
Object Construction Graphs
• Primary Literature Source: ChatUniTest (ISSTA Companion ’25)
• Content Location: Section III.A
• Resource Link: Source Link
Definition
A dependency graph mapping instantiation steps required to construct objects for a unit test.
Structure of Representation
Nodes represent classes or mocks, and directed edges represent constructors, dependencies, or
argument objects.
Example Requirement
The support structure for communicating commands must be reliable, with a uniform ACK/NAK
protocol adopted across all systems. Timeouts must be supported at approximately 500 msec.
Example Test Case
OCG Dependency Chain for CommandSender Test:
MockSocket (arg: timeout=500ms) ----> CommandSender (depends on MockSocket)
CommandSender ----> sendCommand("START")
Assert: returns expected status
25


# Page 26

Summer Project 2026
Test Case Representations Catalog
24
Domain-Specific DSLs
• Primary Literature Source: A-TEST ’24 Workshop Proceedings
• Content Location: Section II
• Resource Link: Source Link
Definition
High-level DSL files mapping abstract test scenarios directly to low-level platform APIs and
system driver calls.
Structure of Representation
A translation mapping where each DSL clause connects to a specific API call (e.g. Gherkin
steps to socket writes).
Example Requirement
The support structure for communicating commands must be reliable, with a uniform ACK/NAK
protocol adopted across all systems. Timeouts must be supported at approximately 500 msec.
Example Test Case
DSL Step Mapping:
- Step: "When a command is sent" -> Maps to: socket.write("PAYLOAD"); start_timer(500);
- Step: "Then a timeout occurs" -> Maps to: assert(elapsed_timer >= 500 && read_buffer ==
26


# Page 27

Summer Project 2026
Test Case Representations Catalog
25
Test Requirement Matrix
• Primary Literature Source: Regression Test Selection (IEEE Access ’20)
• Content Location: Section III
• Resource Link: Source Link
Definition
A traceability matrix mapping test cases to the specific system requirements they cover.
Structure of Representation
A binary 2D grid with rows representing Test Cases and columns representing Requirements.
Example Requirement
The support structure for communicating commands must be reliable, with a uniform ACK/NAK
protocol adopted across all systems. Timeouts must be supported at approximately 500 msec.
Example Test Case
TR Matrix:
| REQ_ACK | REQ_NAK | REQ_TIMEOUT |
-----------+---------+---------+-------------+
TC_ACK_01
|
1
|
0
|
0
|
TC_NAK_01
|
0
|
1
|
0
|
TC_TIME_01 |
0
|
0
|
1
|
-----------+---------+---------+-------------+
27


# Page 28

Summer Project 2026
Test Case Representations Catalog
26
Feature Vectors & Distributions
• Primary Literature Source: A-TEST ’24 Workshop Proceedings
• Content Location: Section II.B
• Resource Link: Source Link
Definition
Multi-dimensional numeric embeddings representing test case parameters to evaluate dataset
coverage and diversity.
Structure of Representation
Floating-point vectors representing test properties, evaluated using nearest-neighbor clustering
algorithms.
Example Requirement
The support structure for communicating commands must be reliable, with a uniform ACK/NAK
protocol adopted across all systems. Timeouts must be supported at approximately 500 msec.
Example Test Case
Test case vector embedding:
V = [command_type_hash, delay_ms, expected_status_code]
V_ACK = [0.85, 120.0, 200.0]
V_TIMEOUT = [0.85, 500.0, 504.0]
Distance: Verify vectors cover a diverse distribution of latency delays from 0ms to 1000ms
28


# Page 29

Summer Project 2026
Test Case Representations Catalog
27
Consumer-Driven Contract
• Primary Literature Source: Martin Fowler (CDC ’06)
• Content Location: Section ”Service Evolution”
• Resource Link: Source Link
Definition
An interface schema defined by the client (consumer) to verify that the backend provider does
not break expectations.
Structure of Representation
A JSON/YAML schema listing exact requests and expected response fields.
Example Requirement
The support structure for communicating commands must be reliable, with a uniform ACK/NAK
protocol adopted across all systems. Timeouts must be supported at approximately 500 msec.
Example Test Case
JSON Contract pact file:
{
"request": {
"method": "POST",
"path": "/command/send",
"body": { "cmd": "STATUS" }
},
"response": {
"status": 200,
"body": { "response": "ACK" }
}
}
29


# Page 30

Summer Project 2026
Test Case Representations Catalog
28
UML Testing Profile (UTP)
• Primary Literature Source: Baker et al. (IEEE ICSTW ’05)
• Content Location: Section 3 / Page 2
• Resource Link: Source Link
Definition
A standardized UML extension defining test architectures, behaviors, and evaluations in model-
driven testing.
Structure of Representation
UML classes and sequences stereotyped with <<TestContext>>, <<TestCase>>, <<SUT>>,
and <<Verdict>>.
Example Requirement
The support structure for communicating commands must be reliable, with a uniform ACK/NAK
protocol adopted across all systems. Timeouts must be supported at approximately 500 msec.
Example Test Case
UTP Model Definitions:
- Class ‘WatchdogTest‘ stereotyped ‘<<TestContext>>‘
- SUT stereotyped ‘<<SUT>>‘
- Operation ‘verifyTimeout‘ stereotyped ‘<<TestCase>>‘
- Validation: checks if response duration >= 500ms, sets ‘<<Verdict>>‘ to FAIL.
30


# Page 31

Summer Project 2026
Test Case Representations Catalog
29
Petri Nets
• Primary Literature Source: Petri Nets Testing (IEEE ICSTW ’08)
• Content Location: Section III / Page 2
• Resource Link: Source Link
Definition
A formal mathematical bipartite graph mapping places, transitions, and token markings to verify
concurrent systems.
Structure of Representation
Bipartite graph N = (P, T, F, M0) where P is places, T is transitions, F is arcs, and M0 is initial
token markings.
Example Requirement
The support structure for communicating commands must be reliable, with a uniform ACK/NAK
protocol adopted across all systems. Timeouts must be supported at approximately 500 msec.
Example Test Case
Petri Net Setup:
- Places P = {Idle, Awaiting, Success, Timeout}
- Transitions T = {send, receive_ack, expire_timer}
- M0 = (1, 0, 0, 0)
- Arcs:
* (Idle, send) -> Awaiting
* Awaiting -- expire_timer (delay >= 500ms) --> Timeout
* Awaiting -- receive_ack (delay < 500ms) --> Success
31


# Page 32

Summer Project 2026
Test Case Representations Catalog
30
Message Sequence Charts
• Primary Literature Source: Testing from MSCs (IEEE ’98)
• Content Location: Section 2 / Page 3
• Resource Link: Source Link
Definition
A standardized graphical language (ITU-T Z.120) that describes message interaction scenarios
between independent system components.
Structure of Representation
Vertical lines representing instances (processes) and horizontal directed arrows representing
message passing, with optional timers.
Example Requirement
The support structure for communicating commands must be reliable, with a uniform ACK/NAK
protocol adopted across all systems. Timeouts must be supported at approximately 500 msec.
Example Test Case
msc command_timeout;
inst Client, Server;
Client -> Server: send_command;
settimeout Client: 500;
Server -> Client: ACK;
timeout Client: stop;
endmsc;
32


# Page 33

Summer Project 2026
Test Case Representations Catalog
31
Temporal Logic (LTL)
• Primary Literature Source: LTL specifications (IEEE TSE ’08)
• Content Location: Section III / Page 5
• Resource Link: Source Link
Definition
A formal logic framework incorporating temporal operators to specify properties of execution
paths over time.
Structure of Representation
Boolean propositions extended with temporal operators: Globally (Always), Eventually, Next,
and Until.
Example Requirement
The support structure for communicating commands must be reliable, with a uniform ACK/NAK
protocol adopted across all systems. Timeouts must be supported at approximately 500 msec.
Example Test Case
LTL Formula:
Always (cmd_sent -> Eventually_within_500ms (received_ACK OR received_NAK))
Formal Notation:
[](cmd_sent -> <>(<= 5) (ack || nak))
(where 1 step = 100ms)
33
