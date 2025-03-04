﻿// Copyright (c) Microsoft Corporation.
// Licensed under the MIT license.
// Learn more about F# at http://fsharp.org
#if INTERACTIVE
#r @"C:\Users\Andrew Fitzgibbon\.nuget\packages\fsharp.compiler.service\25.0.1\lib\netstandard2.0\FSharp.Compiler.Service.dll"
#endif

//We're avoiding requiring projects files so we specify the exact location, is there a better way of doing this?
let netCore310Path = @"dotnet/packs/Microsoft.NETCore.App.Ref/3.1.0/ref/netcoreapp3.1/"
let netCore220Path = @"dotnet/sdk/NuGetFallbackFolder/microsoft.netcore.app/2.2.0/ref/netcoreapp2.2/"

open FSharp.Compiler.SourceCodeServices
open lispgen
open System.IO

// Create an interactive checker instance 
let checker = FSharpChecker.Create(keepAssemblyContents=true)
let exeDirectory = System.IO.Path.GetDirectoryName(System.Reflection.Assembly.GetExecutingAssembly().Location)
let (++) a b = System.IO.Path.Combine(a,b)

let parseAndCheckFiles files = 
    let fsproj = "nul.fsproj" // unused?

    (* adapted for .NET Core from https://fsharp.github.io/FSharp.Compiler.Service/project.html
    *)
    let sysLib nm =
        if System.Environment.OSVersion.Platform = System.PlatformID.Win32NT then

            let windowsPaths = [
                System.Environment.GetFolderPath(System.Environment.SpecialFolder.ProgramFiles) ++ netCore310Path
                System.Environment.GetFolderPath(System.Environment.SpecialFolder.ProgramFiles) ++ netCore220Path
            ]

            windowsPaths
            |> List.tryFind (Directory.Exists)
            |> (function
                | Some path -> path ++ nm + ".dll"
                | None ->
                    failwithf
                        "Can't find .NET Core references, ensure they're installed. Looked in:\n%s"
                        (windowsPaths |> String.concat "\n")
            )
        else
            let otherPaths = [
                "/usr/share/" ++ netCore310Path  // Newer .NET version in WSL/Ubuntu
                "/usr/share/" ++ netCore220Path //WSL/Ubuntu install
                "/usr/share/local/" ++ netCore220Path //macOS install
            ]
            otherPaths
            |> List.tryFind (Directory.Exists)
            |> (function
                | Some path -> path ++ nm + ".dll"
                | None ->
                    failwithf
                        "Can't find .NET Core references, ensure they're installed. Looked in:\n%s"
                        (otherPaths |> String.concat "\n")
            )

    let localLib name =
        exeDirectory ++ name + ".dll"

    // Get context representing a stand-alone (script) file
    let projOptions = checker.GetProjectOptionsFromCommandLineArgs
                            (fsproj,
                                [| yield "--simpleresolution" 
                                   yield "--noframework" 
                                   yield "--debug:full" 
                                   yield "--define:DEBUG" 
                                   yield "--optimize-" 
                                   yield "--doc:test.xml" 
                                   yield "--warn:3" 
                                   yield "--fullpaths" 
                                   yield "--flaterrors" 
                                   yield "--target:library"

                                   yield exeDirectory ++ "Util.fs"
                                   yield exeDirectory ++ "Vector.fs"
                                   yield exeDirectory ++ "Knossos.fs"

                                   yield! files
                                   let references =
                                     [ sysLib "mscorlib" 
                                       sysLib "System"
                                       sysLib "System.Core"
                                       sysLib "System.Runtime"
                                       sysLib "System.Runtime.Extensions"
                                       localLib "FSharp.Core" ]
                                   for r in references do 
                                         yield "-r:" + r
                                   |])
    
    let checkProjectResults = checker.ParseAndCheckProject(projOptions) |> Async.RunSynchronously
    if checkProjectResults.Errors <> [||] then
        let s = checkProjectResults.Errors |> Array.iter (fun (e:FSharpErrorInfo) -> printf "%A: %A\n" e.Severity (e.ToString()))

        if checkProjectResults.Errors|> Array.exists (fun error -> error.Severity = FSharpErrorSeverity.Error) then
            failwith "There were errors"

    checkProjectResults.AssemblyContents.ImplementationFiles
    // TODO: checkProjectResults.GetOptimizedAssemblyContents().ImplementationFiles

[<EntryPoint>]
let main argv =
    if argv.Length < 3 then
        printfn "usage: f2k outfile infiles"
        exit 1
    
    let exe = argv.[0]
    let outFile = argv.[1]
    let files = argv.[2..]

    if File.Exists(outFile) then
        printf "Warning: Overwriting existing file %s\n" outFile

    printfn "f2k: Parsing %d files to %s" (Seq.length files) outFile

    (* e.g. run as:
       dotnet run .\f2k.fsproj ..\..\..\examples\ml-gmm\gmm.fs  
    *)

    for f in files do
        if not (File.Exists(f)) then
            failwithf "Cannot open file %A" f

    let checkedFiles = parseAndCheckFiles files
    // checkedFiles now also contains the stub libraries, so take only the last N 
     
    let prelude = seq {
        yield ";; Prelude: Knossos.ks"
        yield! File.ReadAllLines (exeDirectory ++ "Knossos.ks")
    }
    let decls =
        checkedFiles
        |> Seq.skip (Seq.length checkedFiles - Seq.length files)
        |> Seq.collect (fun implementationFileContent -> seq {            
            yield ";; SRC: " + implementationFileContent.FileName
            yield! lispgen.toLispDecls implementationFileContent
        })
    printfn "f2k: Writing %d + %d lines to file %s" (Seq.length prelude) (Seq.length decls) outFile
    File.WriteAllLines (outFile, (Seq.append prelude decls))
    0
