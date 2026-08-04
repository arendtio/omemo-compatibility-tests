#!/usr/bin/env ruby
# Adds MonalWire CLI target to vendor Monal.xcodeproj and Podfile (idempotent).
require "fileutils"
require "xcodeproj"

root = File.expand_path("../../..", __dir__)
monal_dir = File.join(root, "vendor/monal/Monal")
project_path = File.join(monal_dir, "Monal.xcodeproj")
podfile_path = File.join(monal_dir, "Podfile")
sources_dir = File.join(root, "interop/monal-native/Sources")
info_plist = File.join(root, "interop/monal-native/MonalWire-Info.plist")

unless File.directory?(monal_dir)
  warn "vendor/monal missing at #{monal_dir}"
  exit 1
end

def normalize_monal_wire_target(target, info_plist)
  target.product_type = "com.apple.product-type.application"
  target.build_configurations.each do |config|
    config.build_settings["SWIFT_VERSION"] = "5.0"
    config.build_settings["IPHONEOS_DEPLOYMENT_TARGET"] = "14.0"
    config.build_settings["CODE_SIGNING_ALLOWED"] = "NO"
    config.build_settings["GCC_PREFIX_HEADER"] = "MonalSourceCodePrefix.pch"
    config.build_settings["GCC_PRECOMPILE_PREFIX_HEADER"] = "YES"
    config.build_settings["HEADER_SEARCH_PATHS"] = "$(inherited) $(SRCROOT)/Classes $(SRCROOT)/monalxmpp"
    config.build_settings["INFOPLIST_FILE"] = info_plist
    config.build_settings["PRODUCT_BUNDLE_IDENTIFIER"] = "org.monal-im.MonalWire"
    config.build_settings["PRODUCT_NAME"] = "MonalWire"
    config.build_settings["WRAPPER_EXTENSION"] = "app"
    config.build_settings["ALWAYS_EMBED_SWIFT_STANDARD_LIBRARIES"] = "$(inherited)"
    config.build_settings["LD_RUNPATH_SEARCH_PATHS"] = [
      "$(inherited)",
      "@executable_path/Frameworks",
      "@loader_path/Frameworks",
    ]
    config.build_settings.delete("SWIFT_VERSION[sdk=iphoneos*]")
    config.build_settings.delete("SWIFT_VERSION[sdk=iphonesimulator*]")
  end
end

project = Xcodeproj::Project.open(project_path)
existing = project.targets.find { |t| t.name == "MonalWire" }

unless existing
  group = project.main_group.new_group("MonalWire", sources_dir)
  target = project.new_target(:application, "MonalWire", :ios, "14.0")

  %w[main.m MonalWireClient.m WireBootstrap.m].each do |src|
    file_ref = group.new_file(src)
    target.source_build_phase.add_file_reference(file_ref)
  end

  monalxmpp = project.targets.find { |t| t.name == "monalxmpp" }
  unless monalxmpp
    warn "monalxmpp target missing in Monal.xcodeproj"
    exit 1
  end
  target.add_dependency(monalxmpp)
  target.frameworks_build_phases.add_file_reference(monalxmpp.product_reference)

  sworim_ref = project.files.find { |f| f.path == "sworim.sqlite" }
  target.resources_build_phase.add_file_reference(sworim_ref) if sworim_ref

  normalize_monal_wire_target(target, info_plist)

  project.save
  existing = target
  puts "Added MonalWire target to Monal.xcodeproj"
else
  puts "MonalWire target already present"
  normalize_monal_wire_target(existing, info_plist)
  project.save
end

scheme_dir = File.join(project_path, "xcshareddata/xcschemes")
FileUtils.mkdir_p(scheme_dir)
scheme_path = File.join(scheme_dir, "MonalWire.xcscheme")
scheme = <<~XML
  <?xml version="1.0" encoding="UTF-8"?>
  <Scheme LastUpgradeVersion="1400" version="1.3">
    <BuildAction parallelizeBuildables="YES" buildImplicitDependencies="YES">
      <BuildActionEntries>
        <BuildActionEntry buildForTesting="YES" buildForRunning="YES" buildForProfiling="YES" buildForArchiving="YES" buildForAnalyzing="YES">
          <BuildableReference
            BuildableIdentifier="primary"
            BlueprintIdentifier="#{existing.uuid}"
            BuildableName="MonalWire.app"
            BlueprintName="MonalWire"
            ReferencedContainer="container:Monal.xcodeproj">
          </BuildableReference>
        </BuildActionEntry>
      </BuildActionEntries>
    </BuildAction>
    <TestAction buildConfiguration="Debug" shouldUseLaunchSchemeArgsEnv="YES"/>
    <LaunchAction buildConfiguration="Debug" allowLocationSimulation="YES"/>
    <ProfileAction buildConfiguration="Debug" shouldUseLaunchSchemeArgsEnv="YES"/>
    <AnalyzeAction buildConfiguration="Debug"/>
    <ArchiveAction buildConfiguration="Debug" revealArchiveInOrganizer="YES"/>
  </Scheme>
XML
File.write(scheme_path, scheme)
puts "Wrote #{scheme_path}"

podfile = File.read(podfile_path)
marker = "target 'MonalWire'"
unless podfile.include?(marker)
  podfile << "\n\ntarget 'MonalWire' do\n  monalxmpp\nend\n"
  File.write(podfile_path, podfile)
  puts "Appended MonalWire target to Podfile"
else
  puts "Podfile already has MonalWire target"
end
