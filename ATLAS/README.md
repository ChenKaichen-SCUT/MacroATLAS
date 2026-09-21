## Install
Download the latest release of LTL-Learning.jar from the *[Releases](https://github.com/SteveZhangBit/LTL-Learning/releases)* page.

The program requires Java >= 8 to run.

**Note:**
The tool requires AlloyMax to run. AlloyMax will copy some util modules and solvers to a temp directory. So in order for the tool to run correctly, I suggest clone the repo to your local machine and manually start AlloyMax for the first time.
```
git clone <this repo address>
cd LTL-Learning
java -jar lib/AlloyMax-1.0.3.jar
```
Click the *Execute* button on the GUI. It should find an instance, which indicates that Alloy can successfully run on your machine. Then, you can close the AlloyMax GUI.

**Note:**
The above step may not be necessary because explicitly providing the library path using `-Djava.library.path` can let AlloyMax successfully find the third-party libraries such as OpenWBO.

## Task file
We extend the problem format from [samples2LTL](https://github.com/ivan-gavran/samples2LTL) to define a problem. The file looks like:
```
0,0;0,1;0,1;0,0;0,0::0
0,1;0,1;0,1;0,1;0,1::4
0,0;0,1;0,1;0,1;0,1::3
0,1;0,1;0,0;0,1;0,1::4
0,0;0,0;0,0;0,1;0,0::2
---
1,0;1,1;1,0;1,1;0,0::1
0,0;1,1;1,0;0,1;0,1::0
1,0;1,0;0,1;0,1;0,1::3
0,1;0,0;0,1;1,0;0,1::2
1,0;0,1;1,0;1,0;1,1::3
---
G,F,!,U,&,|,->,X
---
2
---
G(!(x0))
---
<optional constraints and objectives in AlloyMax spec>
```
The first part is the positive traces. Each trace is a sequence of states. Each state is a sequence of atom values `0,0` separated by `,`. States in a trace is separated by `;`. The last `::` indicates after the last state of the trace, where it would go back to for the infinite loop in a lasso trace. When it is omitted, it means the trace goes back to the first state.

For example: `0,0;0,0;0,0;0,1;0,0::2` means there are 5 states in the trace, and after the last state, it will go back to the trace with index 2. The index starts from 0.

The second part is the negative traces.

The third part is the operators to allow in the learned formula. In total, we allow `&, |, ->, !, X, G, F, U`.

The next part is a number that indicates the depth of the syntax tree. However, we are actually using a DAG to model the syntax. So we need the max number of nodes in the graph. For simplicity, we compute the max number of nodes as `2^depth - 1`. So in practice, set the depth to be less or equal to 4, which will allow a maximum of 15 subformulas in the learned LTL.

In addition, a user can also use brackets e.g., `[3]` to enforce the max number of nodes.

The next part is the expected formula. Multiple expected formulas are separated by `;`. This is optional.

The final part is an optional constraints and objectives in AlloyMax spec. Syntax for Alloy can be found [here](https://alloytools.org/documentation.html).

## Run
The usage of our tool is as follows:
```
Usage: Atlas [OPTIONS]

  A tool to learn LTL formulas from a set of positive and negative examples by
  using AlloyMax.

Options:
  --_run TEXT          Run the learning process. YOU SHOULD NOT USE THIS.
                       INTERNAL USE ONLY.
  -s, --solver TEXT    The AlloyMax solver to use. Default: SAT4JMax
  -f, --filename TEXT  The file containing one task to run.
  -t, --traces TEXT    The folder containing the tasks to run. It will find
                       all task files under the folder recursively.
  -T, --timeout INT    The timeout in seconds for solving each task.
  -m, --model          Print the model to use for learning.
  -A, --findAny        Find any solution. Default: false
  -e, --expected       Enumerate until the expected formula found.
  -h, --help           Show this message and exit
```

For example, to run a particular task file. Note that, the task file should be ending with `.trace`. Then, you can do:
```
java -Djava.library.path=./lib -cp LTL-Learning.jar cmu.s3d.ltl.app.CLIKt -f <the trace file> -s OpenWBOWeighted -T 60
```
In this example, we use `-Djava.library.path=./lib/open-wbo` to add the open-wbo MaxSAT Solver by Ruben Martins to the path, and we use `OpenWBOWeighted` as the solving algorithm. This is recommended because it is the fastest one from our benchmark.

The result of the above example task file should look like:
```
<trace file path>,5,5,2,2,5,"G(!(x0))",0.495,"!(F(x0))"
```

**Note:** The learned LTL might be different from the expected one for two reasons: (1) they are actually equal like "G(!x0) <=> !F(x0)"; (2) there exists a smaller LTL formula satisfying the examples traces.

## Benchmark
The benchmark problems are located in the `benchmarks` folder. The results are located in the `benchmark_results` folder.
