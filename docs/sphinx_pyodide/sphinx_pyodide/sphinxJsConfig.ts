import {
  Application,
  DeclarationReflection,
  ProjectReflection,
  ReflectionType,
} from 'typedoc'
import { Attribute, IRFunction, TopLevelIR } from 'sphinx_js/ir'

declare module 'typedoc' {
  export interface Application {
    extraData: {
      ffiFields: string[]
      pyproxyMethods: [string, (Attribute | IRFunction)[]][]
    }
  }
}

function shouldDestructureArg(param) {
  return param.name === 'options'
}

function calculateFfiFields(project: ProjectReflection): string[] {
  const ffiMod = project.getChildByName('js/ffi')
  const ffi = ffiMod?.getChildByName('ffi') as DeclarationReflection
  const refl = ffi.type as ReflectionType
  const result = refl.declaration.children?.map((x) => x.name)
  if (!result) {
    throw new Error('Failed to calculate ffi fields')
  }
  return result
}

function calculatePyProxyMethods(
  typeDocToIRMap: Map<DeclarationReflection, TopLevelIR>,
): [string, (Attribute | IRFunction)[]][] {
  const pyproxyMethods: [string, (Attribute | IRFunction)[]][] = []
  for (const [key, value] of typeDocToIRMap.entries()) {
    value.exported_from = null
    if (value.kind === 'attribute' || value.kind === 'function') {
      value.is_private = key.flags.isExternal || key.flags.isPrivate
    }

    if (value.kind !== 'class') {
      continue
    }
    if (value.modifier_tags.includes('@hideconstructor')) {
      value.constructor_ = null
    }
    if (value.deppath === './core/pyproxy' && value.name.endsWith('Methods')) {
      pyproxyMethods.push([value.name, value.members])
    }
  }
  return pyproxyMethods
}

function postConvert(
  app: Application,
  project: ProjectReflection,
  typeDocToIRMap: Map<DeclarationReflection, TopLevelIR>,
) {
  app.extraData.ffiFields = calculateFfiFields(project)
  app.extraData.pyproxyMethods = calculatePyProxyMethods(typeDocToIRMap)
}

export const config = {
  shouldDestructureArg,
  postConvert,
}
